"""Un color por grupo bancario, el mismo en todas las vistas del explorador.

Paleta Okabe-Ito (apta para daltonismo), con colores que se distinguen sobre fondo blanco. El explorador
recibe estos valores desde su generador: cambiar un color es cambiarlo acá.
"""

from __future__ import annotations

COLORES_GRUPO: dict[str, str] = {
    "GBM": "#0072B2",
    "GBID": "#E69F00",
    "CAF": "#009E73",
    "NDB": "#D55E00",
    "AIIB": "#CC79A7",
    "FONPLATA": "#56B4E9",
    "BCIE": "#555555",
}
