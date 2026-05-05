package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.PurchaseVerifyRequest
import com.example.mbtichatfriend.data.remote.PurchaseVerifyResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class BillingRepository @Inject constructor(
    private val api: ChatApi,
) {
    suspend fun verifyPurchase(
        userId: String,
        purchaseToken: String,
        orderId: String,
        productId: String,
    ): Result<PurchaseVerifyResponse> = runCatching {
        api.verifyPurchase(
            PurchaseVerifyRequest(userId, purchaseToken, orderId, productId)
        )
    }
}
