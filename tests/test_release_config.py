"""The release secret in Config: validated, hashed as a keyed digest, never shown or written."""
import pytest

import arthasim
from arthasim import Config

SECRET = "0f" * 32


def test_hash_unchanged_without_a_secret():
    assert Config.tier("S").hash() == "22ed10f6ba78d66b6da6ca2b35d8345aa048f86b4b75de27ead52c4a5b5ddd79"
    assert Config.tier("XS").hash() == "10ae0bac368e147423c3854d946546d66d3705527f432bba5209cdaa224768c7"


def test_secret_changes_the_hash_and_never_shows():
    a, b = Config.tier("S", release_secret=SECRET), Config.tier("S", release_secret="1e" * 32)
    assert len({Config.tier("S").hash(), a.hash(), b.hash()}) == 3
    assert SECRET not in repr(a) and SECRET not in str(a) and SECRET not in a.hash()
    assert a.secret_bytes() == bytes.fromhex(SECRET) and Config.tier("S").secret_bytes() is None
    assert Config.tier("S", release_secret=SECRET.upper()).hash() == a.hash()


@pytest.mark.parametrize("bad", ["ab" * 15 + "a", "0x" + "ab" * 16, " " + "ab" * 16, "ab" * 16 + "g",
                                 "ab" * 15 + "abc"])
def test_malformed_secret_is_rejected(bad):          # Review Focus 1
    with pytest.raises(ValueError, match="release_secret"):
        Config.tier("S", release_secret=bad)


def test_to_yaml_never_writes_the_secret(tmp_path):  # Review Focus 2
    a = Config.tier("S", release_secret=SECRET)
    a.to_yaml(tmp_path / "c.yaml")
    assert SECRET not in (tmp_path / "c.yaml").read_text()
    back = Config.from_yaml(tmp_path / "c.yaml")
    assert back.release_secret is None and back.hash() == Config.tier("S").hash() != a.hash()


def test_new_release_secret():
    s = arthasim.new_release_secret()
    assert len(s) == 64 and Config.tier("S", release_secret=s).secret_bytes() == bytes.fromhex(s)
