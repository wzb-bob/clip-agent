"""逐镜素材智能分配——真人剪辑师的素材选择逻辑

规则:
  1. 逐镜匹配: shot_type/emotion/camera_move→素材特征匹配
  2. 不重复: 相邻镜头不重复用同一素材
  3. 优先级: hook(钩子)和CTA(行动号召)优先选最佳素材
  4. 多样性: 同一素材最多用2次·全程不超过30%
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 景别→素材类型映射
SHOT_TO_MATERIAL = {
    "特写": ["product", "talking_close"],
    "近景": ["talking", "talking_close"],
    "中近景": ["talking", "broll"],
    "中景": ["broll", "environment"],
    "全景": ["environment", "broll"],
    "远景": ["environment"],
    "俯拍": ["product", "environment"],
}

# 情绪→素材偏好(优先匹配)
EMOTION_MATERIAL = {
    "冲击": {"prefer": "product", "reason": "冲击感需要产品特写"},
    "共鸣": {"prefer": "talking", "reason": "共鸣需要人脸表情"},
    "信任": {"prefer": "talking", "reason": "信任需要眼神接触"},
    "渴望": {"prefer": "product", "reason": "渴望需要产品诱惑"},
    "紧迫": {"prefer": "environment", "reason": "紧迫需要环境氛围"},
    "好奇": {"prefer": "broll", "reason": "好奇需要背后揭秘"},
}


@dataclass
class ShotMaterialAssignment:
    """单镜素材分配结果"""
    shot_index: int
    shot_type: str
    emotion: str
    script_text: str
    assigned_material: str       # 素材文件路径
    material_type: str           # talking/product/broll/environment
    match_score: float           # 0-1 匹配度
    priority: int                # 1=最高(hook/CTA) 2=普通
    used_count: int = 0          # 该素材已被用次数
    broll_overlay: bool = False  # B-roll覆盖口播画面·保留原音频
    audio_replace: bool = False  # TTS替换原音频·用于数字人口播


def _calc_shot_priority(index: int, total: int, emotion: str) -> int:
    """镜头优先级: hook(前2镜)=1, CTA(末镜)=1, 其余=2"""
    if index <= 1 or emotion == "冲击":
        return 1  # 钩子镜头+冲击情绪=最高优先
    if index >= total - 1:
        return 1  # CTA镜头=最高优先
    return 2


def _match_score(shot_type: str, emotion: str, material_type: str,
                 has_face: bool, material_score: float) -> float:
    """单镜→单素材匹配度 0-1"""
    score = 0.5  # baseline

    # 景别匹配: shot需要的类型 vs 素材实际类型
    expected = SHOT_TO_MATERIAL.get(shot_type, ["talking"])
    if material_type in expected:
        score += 0.25

    # 情绪偏好
    emo_pref = EMOTION_MATERIAL.get(emotion, {})
    if emo_pref.get("prefer") == material_type:
        score += 0.15

    # 人脸匹配(口播镜头必须有人脸)
    if material_type == "talking" and not has_face:
        score -= 0.4

    # 素材质量加权
    score += material_score * 0.1

    return round(min(1.0, max(0.0, score)), 3)


def assign_materials_to_shots(
    shot_json: list[dict],
    materials: dict[str, dict],   # {path: {"type":str, "score":float, "has_face":bool}}
    script_text: str = "",
) -> list[ShotMaterialAssignment]:
    """逐镜分配素材·真人剪辑师的选择逻辑

    Args:
        shot_json: [{"shot_type","emotion","script_text","camera_move"}, ...]
        materials: {file_path: {"type":"talking","score":0.8,"has_face":True}, ...}

    Returns:
        按shot顺序的分配结果列表
    """
    if not shot_json:
        return []

    total_shots = len(shot_json)
    assignments = []
    used_count: dict[str, int] = {}  # {path: 使用次数}
    last_material: str = ""           # 上一个用的素材·避免相邻重复

    # 按优先级排序: 先分配P1(hook/CTA), 再P2
    shots_with_priority = sorted(
        enumerate(shot_json),
        key=lambda x: _calc_shot_priority(x[0], total_shots,
                                          x[1].get("emotion", "")),
    )

    temp_assignments: dict[int, ShotMaterialAssignment] = {}

    for shot_idx, shot in shots_with_priority:
        shot_type = shot.get("shot_type", "中景")
        emotion = shot.get("emotion", "")
        text = shot.get("script_text", "")[:30]
        priority = _calc_shot_priority(shot_idx, total_shots, emotion)

        best_match = None
        best_score = -1.0

        for mat_path, mat_info in materials.items():
            mat_type = mat_info.get("type", "talking")
            mat_score = mat_info.get("score", 0.5)
            has_face = mat_info.get("has_face", False)

            # 品类可用性: talking_head镜头必须有人脸素材
            if mat_type == "talking" and not has_face:
                continue

            score = _match_score(shot_type, emotion, mat_type, has_face, mat_score)

            # 惩罚重复使用(同一素材最多2次)
            if used_count.get(mat_path, 0) >= 2:
                score -= 0.3
            if used_count.get(mat_path, 0) >= 1:
                score -= 0.1

            # 惩罚相邻重复
            if mat_path == last_material and shot_idx > 0:
                score -= 0.5

            if score > best_score:
                best_score = score
                best_match = mat_path

        if best_match:
            used_count[best_match] = used_count.get(best_match, 0) + 1
            mat_type = materials[best_match].get("type", "?")

            # B-roll覆盖: 素材非口播但镜头需人物→覆盖画面保留原声
            is_overlay = (mat_type in ("broll", "environment", "product")
                         and shot_type in ("近景", "中近景", "中景"))

            # 音频替换: 无口播素材时标记TTS替换
            needs_audio = (mat_type != "talking" and priority == 1
                          and shot_type in ("特写", "近景"))

            assignment = ShotMaterialAssignment(
                shot_index=shot_idx + 1,
                shot_type=shot_type,
                emotion=emotion,
                script_text=text,
                assigned_material=best_match,
                material_type=mat_type,
                match_score=best_score,
                priority=priority,
                used_count=used_count[best_match],
                broll_overlay=is_overlay,
                audio_replace=needs_audio,
            )
            temp_assignments[shot_idx] = assignment
            last_material = best_match

    # 按shot顺序返回
    for i in range(total_shots):
        if i in temp_assignments:
            assignments.append(temp_assignments[i])
        else:
            # 无匹配素材·用第一个可用
            first_mat = next(iter(materials.keys()), "") if materials else ""
            assignments.append(ShotMaterialAssignment(
                shot_index=i + 1, shot_type=shot_json[i].get("shot_type","?"),
                emotion=shot_json[i].get("emotion",""),
                script_text=shot_json[i].get("script_text","")[:30],
                assigned_material=first_mat,
                material_type="talking", match_score=0.3, priority=2, used_count=99,
            ))

    # 多样性报告
    unique_mats = len(set(a.assigned_material for a in assignments))
    logger.info("逐镜分配: %d镜→%d个不同素材·多样性=%.0f%%",
               total_shots, unique_mats,
               unique_mats / max(1, total_shots) * 100)

    return assignments


def material_variety_report(assignments: list[ShotMaterialAssignment]) -> dict:
    """素材多样性报告"""
    total = len(assignments)
    if not total:
        return {"total_shots": 0, "unique_materials": 0, "diversity": 0}

    unique = len(set(a.assigned_material for a in assignments))
    repeated = sum(1 for a in assignments if a.used_count > 1)
    priority_ok = sum(1 for a in assignments
                      if a.priority == 1 and a.match_score >= 0.6)

    return {
        "total_shots": total,
        "unique_materials": unique,
        "diversity": round(unique / total, 2),
        "repeated_shots": repeated,
        "priority_shots_ok": priority_ok,
        "avg_match_score": round(
            sum(a.match_score for a in assignments) / total, 3),
    }
