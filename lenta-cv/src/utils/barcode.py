"""Barcode normalization and validation helpers."""


def normalize_barcode(value: str) -> str:
    """Return only digits from a barcode-like value."""
    return "".join(char for char in str(value or "") if char.isdigit())


def is_valid_ean13(value: str) -> bool:
    """Return whether a value is a valid EAN-13 barcode."""
    barcode = normalize_barcode(value)
    if len(barcode) != 13:
        return False

    digits = [int(char) for char in barcode]
    checksum_sum = sum(
        digits[index] * (1 if index % 2 == 0 else 3)
        for index in range(12)
    )
    check_digit = (10 - (checksum_sum % 10)) % 10
    return check_digit == digits[12]


if __name__ == "__main__":
    assert is_valid_ean13("5012909010825")
    assert is_valid_ean13("2099999089583")
    assert not is_valid_ean13("2099999089588")
    print("EAN-13 self-check passed")
