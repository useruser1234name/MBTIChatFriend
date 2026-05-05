package com.example.mbtichatfriend.ui.premium

import android.app.Activity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.QueryProductDetailsParams
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.PurchaseVerifyRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── 36차 스프린트: 프리미엄 구독 ViewModel (인앱결제 + API 연동) ──────────────

data class PremiumUiState(
    val isSubscribed: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class PremiumViewModel @Inject constructor(
    private val billingClient: BillingClient,
    private val chatApi: ChatApi
) : ViewModel() {

    private val _uiState = MutableStateFlow(PremiumUiState())
    val uiState: StateFlow<PremiumUiState> = _uiState.asStateFlow()

    private var premiumProductDetails: ProductDetails? = null

    init {
        queryProductDetails()
    }

    private fun queryProductDetails() {
        val productList = listOf(
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId("mbtichat_premium_monthly")
                .setProductType(BillingClient.ProductType.SUBS)
                .build()
        )
        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(productList)
            .build()

        billingClient.queryProductDetailsAsync(params) { _, productDetailsList ->
            premiumProductDetails = productDetailsList.firstOrNull()
        }
    }

    fun subscribe(activity: Activity? = null) {
        val productDetails = premiumProductDetails ?: run {
            _uiState.value = _uiState.value.copy(errorMessage = "상품 정보를 불러오는 중입니다.")
            return
        }
        val activity = activity ?: run {
            _uiState.value = _uiState.value.copy(errorMessage = "결제를 시작할 수 없어요.")
            return
        }

        val offerToken = productDetails.subscriptionOfferDetails?.firstOrNull()?.offerToken ?: return

        val productDetailsParamsList = listOf(
            BillingFlowParams.ProductDetailsParams.newBuilder()
                .setProductDetails(productDetails)
                .setOfferToken(offerToken)
                .build()
        )
        val billingFlowParams = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(productDetailsParamsList)
            .build()

        billingClient.launchBillingFlow(activity, billingFlowParams)
    }

    // subscribe() 오버로드 — Activity 없이 호출 시 (Composable에서 직접 호출용)
    fun subscribe() {
        _uiState.value = _uiState.value.copy(isLoading = true)
        // 실제 Activity는 Composable 레이어에서 주입 필요;
        // 여기서는 상태만 업데이트하고 UI에서 Activity 기반 호출 유도
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                errorMessage = "결제 화면을 불러오는 중이에요."
            )
        }
    }

    fun verifyPurchase(userId: String, purchaseToken: String, orderId: String, productId: String) {
        viewModelScope.launch {
            runCatching {
                val response = chatApi.verifyPurchase(
                    PurchaseVerifyRequest(
                        userId = userId,
                        purchaseToken = purchaseToken,
                        orderId = orderId,
                        productId = productId
                    )
                )
                if (response.success) {
                    _uiState.value = _uiState.value.copy(isSubscribed = true)
                }
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }
}
