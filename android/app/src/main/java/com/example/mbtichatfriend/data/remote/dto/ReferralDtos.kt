package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── 레퍼럴 모델 ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralRedeemResponse(
    val success: Boolean,
    val message: String = "",
    @Json(name = "bonus_days") val bonusDays: Int = 0
)

// ── 레퍼럴 V2 통계 모델 (27차 스프린트) ──────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralStatsResponse(
    @Json(name = "invited_count") val invitedCount: Int = 0,
    @Json(name = "reward_days") val rewardDays: Int = 0
)

// ── 레퍼럴 V3 딥링크 모델 (29차 스프린트) ────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralLinkResponse(
    @Json(name = "referral_link") val referralLink: String,
    @Json(name = "referral_code") val referralCode: String,
)

@JsonClass(generateAdapter = false)
data class RedeemRequest(
    @Json(name = "code") val code: String,
)
