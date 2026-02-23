package com.example.mbtichatfriend.ui.gallery

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.model.PresetCharacter
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class GalleryViewModel @Inject constructor(
    private val characterRepo: CharacterRepository
) : ViewModel() {

    fun addFromPreset(preset: PresetCharacter, onAdded: (Long) -> Unit) {
        viewModelScope.launch {
            val id = characterRepo.addFromPreset(preset)
            onAdded(id)
        }
    }
}
