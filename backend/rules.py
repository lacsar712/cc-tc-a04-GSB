"""双路判定：左右差值绝对值越过登记表门槛即双路超差；单路绝对值不超过 3.0 mm 为合格。"""
LIMIT_MM = 3.0


def judge_pair(left_mm: float, right_mm: float) -> tuple[str, str]:
    over = [
        f"{side} {value} mm"
        for side, value in (("左", left_mm), ("右", right_mm))
        if abs(value) > LIMIT_MM
    ]
    if not over:
        return "合格", f"左 {left_mm} mm、右 {right_mm} mm 均在 ±{LIMIT_MM} mm 以内"
    return "超限", "、".join(over) + f" 超过 ±{LIMIT_MM} mm"


def dual_diff(left_mm: float, right_mm: float) -> float:
    return round(left_mm - right_mm, 3)


def dual_reject_reason(left_mm: float, right_mm: float, threshold_mm: float) -> str | None:
    """左右差值绝对值越过门槛 → 整份退回并写明双路超差。"""
    diff = abs(dual_diff(left_mm, right_mm))
    if diff > threshold_mm:
        return (
            f"双路超差：|{left_mm} - {right_mm}| = {diff} mm "
            f"越过门槛 {threshold_mm} mm，整份退回"
        )
    return None
