class OutOfPolicyRefundFilter:
    """
    Returns True when a refund tool call exceeds the allowed threshold.
    """
    def __init__(self, threshold: int = 200):
        self.threshold = int(threshold)

    def __call__(self, tool_name: str, amount: int) -> bool:
        return tool_name == "refund" and int(amount) > self.threshold
