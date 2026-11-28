"""Công cụ tra cứu đơn hàng và tồn kho (chỉ đọc)."""

ORDERS = {
    "DH-101": {"status": "dang_giao", "sku": "SKU-A1"},
    "DH-102": {"status": "cho_xac_nhan", "sku": "SKU-B2"},
}

INVENTORY = {
    "SKU-A1": 12,
    "SKU-B2": 0,
}


def get_order_status(order_id: str) -> str:
    """Trả trạng thái đơn hàng theo mã đơn (chỉ đọc)."""
    item = ORDERS.get(order_id.strip())
    if not item:
        return "Không tìm thấy mã đơn hàng."
    return f"Đơn {order_id}: trạng thái={item['status']}, sku={item['sku']}"


def check_inventory(sku: str) -> str:
    """Trả số lượng tồn kho của mã sản phẩm (chỉ đọc)."""
    qty = INVENTORY.get(sku.strip())
    if qty is None:
        return "Không tìm thấy mã SKU."
    return f"SKU {sku}: còn {qty} sản phẩm"
