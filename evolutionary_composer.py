"""
Evolutionary Composer Microservice - Generates music from DNA parameters
Replaces generate_music.py with evolutionary capabilities
"""
import numpy as np
import random
import logging
import json
import hashlib
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import soundfile as sf
import scipy.signal as signal
from enum import Enum

logger = logging.getLogger(__name__)

class Waveform(Enum):
    """Synthesizer waveform types"""
    SINE = "sine"
    SAWTOOTH = "sawtooth"
    SQUARE = "square"
    TRIANGLE = "triangle"
    NOISE = "noise"

class ArpPattern(Enum):
    """Arpeggio patterns"""
    UP = "up"
    DOWN = "down"
    UP_DOWN = "up_down"
    RANDOM = "random"
    CUSTOM = "custom"

@dataclass
class MusicDNA:
    """Complete DNA representation for music generation"""
    # Core parameters
    bpm: float = 100.0
    key: str = "C_minor"
    time_signature: Tuple[int, int] = (4, 4)
    duration_seconds: float = 180.0
    
    # Synth parameters
    lead_waveform: Waveform = Waveform.SAWTOOTH
    bass_waveform: Waveform = Waveform.SQUARE
    pad_waveform: Waveform = Waveform.SINE
    
    # Filter parameters
    filter_cutoff_hz: float = 1000.0
    filter_resonance: float = 0.5
    filter_envelope_amount: float = 0.3
    
    # Arpeggio parameters
    arp_pattern: ArpPattern = ArpPattern.UP_DOWN
    arp_speed: float = 0.25  # Notes per beat
    arp_octaves: int = 2
    arp_notes: List[int] = None  # MIDI note offsets
    
    # Effects parameters
    reverb_amount: float = 0.3
    delay_amount: float = 0.2
    chorus_amount: float = 0.1
    distortion_amount: float = 0.05
    
    # Percussion parameters
    kick_pattern: List[float] = None
    snare_pattern: List[float] = None
    hat_pattern: List[float] = None
    percussion_complexity: float = 0.5
    
    # Structural parameters
    intro_length_bars: int = 4
    verse_length_bars: int = 16
    chorus_length_bars: int = 8
    breakdown_length_bars: int = 8
    outro_length_bars: int = 4
    
    def __post_init__(self):
        """Initialize default values"""
        if self.arp_notes is None:
            self.arp_notes = [0, 4, 7, 12]  # Basic minor chord
        
        if self.kick_pattern is None:
            self.kick_pattern = [1.0, 0.0, 0.3, 0.0] * 4
        
        if self.snare_pattern is None:
            self.snare_pattern = [0.0, 0.8, 0.0, 0.5] * 4
        
        if self.hat_pattern is None:
            self.hat_pattern = [0.4] * 16

class EvolutionaryComposer:
    """Generates audio from DNA parameters with evolutionary capabilities"""
    
    def __init__(self, sample_rate: int = 44100):
        """
        Initialize the composer
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        logger.info(f"Evolutionary Composer initialized at {sample_rate}Hz")
    
    def generate_from_dna(self, dna: MusicDNA, output_path: str = None) -> np.ndarray:
        """
        Generate audio from DNA parameters
        
        Args:
            dna: MusicDNA object containing parameters
            output_path: Optional path to save WAV file
            
        Returns:
            Stereo audio array shape (samples, 2)
        """
        try:
            logger.info(f"Generating track from DNA: BPM={dna.bpm}, Key={dna.key}")
            
            # Calculate total samples
            total_samples = int(dna.duration_seconds * self.sample_rate)
            
            # Generate tracks for each element
            lead_track = self._generate_lead(dna, total_samples)
            bass_track = self._generate_bass(dna, total_samples)
            pad_track = self._generate_pad(dna, total_samples)
            percussion_track = self._generate_percussion(dna, total_samples)
            
            # Mix tracks with appropriate levels
            mix = self._mix_tracks(
                lead_track * 0.3,
                bass_track * 0.25,
                pad_track * 0.2,
                percussion_track * 0.35
            )
            
            # Apply global effects
            mix = self._apply_effects(mix, dna)
            
            # Ensure stereo output
            if mix.ndim == 1:
                mix = np.stack([mix, mix], axis=1)
            
            # Normalize to prevent clipping
            max_val = np.max(np.abs(mix))
            if max_val > 0.9:
                mix = mix * (0.9 / max_val)
            
            # Save if output path provided
            if output_path:
                sf.write(output_path, mix, self.sample_rate)
                logger.info(f"Saved audio to {output_path}")
            
            return mix
            
        except Exception as e:
            logger.error(f"Failed to generate audio from DNA: {str(e)}")
            raise
    
    def _generate_lead(self, dna: MusicDNA, total_samples: int) -> np.ndarray:
        """Generate lead arpeggio track"""
        # Calculate timing
        beat_length = 60.0 / dna.bpm
        arp_interval = beat_length / dna.arp_speed