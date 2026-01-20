"""
Groove Extractor - Extrae humanización de grabaciones jamaicanas

Este módulo analiza grabaciones de audio y extrae:
- Timing exacto de cada golpe (onset detection)
- Velocidad estimada de cada golpe
- Desviación respecto a la rejilla teórica (humanización)

Los datos se guardan en database.xlsx en las hojas:
- REJILLAS: Posiciones de golpes (1/0) para cada paso 1-16
- HUMANIZACION: Velocities (V1-V16) y timings (T1-T16) detallados
"""

__version__ = "1.0.0"
