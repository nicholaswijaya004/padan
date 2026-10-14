from padan.fetch import sha256_hex


def test_sha256_of_empty_input_matches_known_value() -> None:
    # The SHA-256 of zero bytes is a published constant:
    # if this passes, we're calling the real SHA-256.
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_same_input_gives_same_hash() -> None:
    hash1 = sha256_hex(b"hello, world!")
    hash2 = sha256_hex(b"hello, world!")
    assert hash1 == hash2


def test_one_byte_change_gives_different_hash() -> None:
    hash1 = sha256_hex(b"openapi: 3.0.0")
    hash2 = sha256_hex(b"openapi: 3.0.1")
    assert hash1 != hash2
