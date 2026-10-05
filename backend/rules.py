"""收敛判定：绝对值不超过 3.0 mm 为合格。"""
LIMIT_MM = 3.0


def judge(delta_mm: float) -> tuple[str, str]:
    if abs(delta_mm) <= LIMIT_MM:
        return "合格", f"收敛 {delta_mm} mm 在 ±{LIMIT_MM} mm 以内"
    return "超限", f"收敛 {delta_mm} mm 超过 ±{LIMIT_MM} mm"


def diff_check(left_mm: float, right_mm: float, threshold_mm: float) -> tuple[float, str | None]:
    """双路门槛：左右差值绝对值越过门槛则整份退回，写明双路超差。"""
    diff = round(abs(left_mm - right_mm), 6)
    if diff > threshold_mm:
        return diff, f"双路超差：左右差值 {diff} mm 越过门槛 {threshold_mm} mm，整份退回"
    return diff, None


def judge_dual(left_mm: float, right_mm: float) -> tuple[str, str]:
    """双路结论：左右两路各自都不超限才合格。"""
    if abs(left_mm) <= LIMIT_MM and abs(right_mm) <= LIMIT_MM:
        return "合格", f"左 {left_mm} mm、右 {right_mm} mm 均在 ±{LIMIT_MM} mm 以内"
    return "超限", f"左 {left_mm} mm、右 {right_mm} mm 超出 ±{LIMIT_MM} mm"
