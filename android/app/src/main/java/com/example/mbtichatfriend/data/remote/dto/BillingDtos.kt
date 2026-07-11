package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── Play Billing 결제 검증 모델 ──────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class PurchaseVerifyRequest(
    @Json(name = "user_id") val userId: String,
    @Json(name = "purchase_token") val purchaseToken: String,
    @Json(name = "order_id") val orderId: String,
    @Json(name = "product_id") val productId: String,
)

@JsonClass(generateAdapter = false)
data class PurchaseVerifyResponse(
    val success: Boolean,
    val plan: String,
    @Json(name = "user_id") val userId: String,
)
