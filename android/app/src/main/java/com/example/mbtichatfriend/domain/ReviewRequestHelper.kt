package com.example.mbtichatfriend.domain

import android.app.Activity

object ReviewRequestHelper {
    fun requestReviewIfEligible(activity: Activity, qualitySessionCount: Int) {
        // Play Core Review is optional in this build; keep the call site safe.
        @Suppress("UNUSED_EXPRESSION")
        activity to qualitySessionCount
    }
}
