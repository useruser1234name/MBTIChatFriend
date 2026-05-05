from app.scopes import build_legacy_cleanup_warnings


def test_legacy_cleanup_warnings_empty_without_legacy_identifiers():
    assert build_legacy_cleanup_warnings() == []


def test_legacy_cleanup_warnings_include_global_vector_store_notice():
    assert build_legacy_cleanup_warnings(character_id="7") == [
        "legacy_global_vector_store_requires_manual_cleanup",
    ]


def test_legacy_cleanup_warnings_include_shared_memory_notice():
    assert build_legacy_cleanup_warnings(character_name="하루", nickname="테스트") == [
        "legacy_shared_memory_key_requires_manual_cleanup",
    ]


def test_legacy_cleanup_warnings_include_both_notices():
    assert build_legacy_cleanup_warnings(
        character_id="7",
        character_name="하루",
        nickname="테스트",
    ) == [
        "legacy_global_vector_store_requires_manual_cleanup",
        "legacy_shared_memory_key_requires_manual_cleanup",
    ]
