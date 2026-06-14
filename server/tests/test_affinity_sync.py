"""호감도 동기화 (affinity mirroring) 테스트.

AffinitySyncRequest/AffinityResponse 스키마의 범위 검증을 확인한다.
"""

import pytest


def test_affinity_sync_request_validation():
    """AffinitySyncRequest 스키마 범위 검증 (score 0-100, level 1-5)."""
    from app.routers.relationship import AffinitySyncRequest
    from pydantic import ValidationError

    req = AffinitySyncRequest(room_id="uid:char1", character_id="char1", score=50, level=3)
    assert req.score == 50
    assert req.level == 3

    with pytest.raises(ValidationError):
        AffinitySyncRequest(room_id="uid:char1", character_id="char1", score=101, level=1)

    with pytest.raises(ValidationError):
        AffinitySyncRequest(room_id="uid:char1", character_id="char1", score=50, level=6)


def test_affinity_response_model():
    """AffinityResponse 스키마 정상 생성."""
    from app.routers.relationship import AffinityResponse

    resp = AffinityResponse(room_id="uid:char1", character_id="char1", score=75, level=4)
    assert resp.score == 75
    assert resp.level == 4
