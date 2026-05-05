package com.example.mbtichatfriend.data.remote

import org.json.JSONObject
import retrofit2.HttpException

class ApiErrorException(
    override val message: String,
    val statusCode: Int? = null
) : Exception(message)

fun toApiErrorException(
    statusCode: Int?,
    rawBody: String?,
    fallbackMessage: String
): ApiErrorException {
    val parsedMessage = parseApiErrorMessage(rawBody, fallbackMessage)
    return ApiErrorException(parsedMessage, statusCode)
}

fun toApiErrorException(
    error: HttpException,
    fallbackMessage: String
): ApiErrorException {
    val rawBody = runCatching {
        error.response()?.errorBody()?.string()
    }.getOrNull()
    return toApiErrorException(error.code(), rawBody, fallbackMessage)
}

private fun parseApiErrorMessage(rawBody: String?, fallbackMessage: String): String {
    val body = rawBody?.trim().orEmpty()
    if (body.isEmpty()) {
        return fallbackMessage
    }

    if (body.startsWith("{")) {
        val detail = runCatching {
            JSONObject(body).optString("detail").trim()
        }.getOrNull().orEmpty()
        if (detail.isNotEmpty()) {
            return detail
        }
    }

    return body.ifEmpty { fallbackMessage }
}
