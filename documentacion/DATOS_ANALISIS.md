# Datos de Análisis

Resultados de análisis para 5 personas del Registro Nacional de Costa Rica.

## Personas analizadas

| Carpeta | Nombre | Cédula | Fincas | Vehículos | Alertas |
|---------|--------|--------|--------|-----------|---------|
| `ALEJANDRA_207420093/` | ALEJANDRA MARIA VARGAS SABORIO | 207420093 | 1 | 0 | 3 |
| `EVELIO_202830740/` | EVELIO CHACON CASTRO | 202830740 | 4 | 1 (Suzuki Grand Vitara) | 0 |
| `MARIA_203170516/` | MARIA AZUCENA RAMIREZ ARIAS | 203170516 | 6 | 1 (Suzuki Grand Vitara) | 9 |
| `MARIANA_205940925/` | MARIANA CHACON RAMIREZ | 205940925 | 1 | 1 (Hyundai Tucson) | 0 |
| `MELISA_205390457/` | MELISA ALEJANDRA CHACON RAMIREZ | 205390457 | 1 | 1 (Freedom motorcycle) | 4 |

## Estructura de cada persona

```
{NOMBRE}_{CEDULA}/
├── analisis.md              ← Reporte generado por MiniMax
├── bienes_muebles/          ← Consultas de bienes muebles
├── catastro_planos/         ← Planos catastrales
├── documentos_diario/       ← Documentos de diario
├── gravamenes_hipotecas/    ← Gravámenes e hipotecas
└── historia_fincas/         ← Historial de fincas
```

Cada subdirectorio contiene archivos en formato JSON, HTML y TXT.

## Datos adicionales de fincas

- `rnp_203170516_fincas/` — queries de fincas 01-06 de MARIA_203170516
- `rnp_203170516_fincas_v2/` — repulled actualizado de las mismas fincas

## Tipos de alertas detectadas

| Tipo | Severidad | Descripción |
|------|-----------|-------------|
| HIPOTECA | high | Hipoteca activa sobre la propiedad |
| SERVIDUMBRE | medium | Servidumbre registrada |
| CONDIC | medium | Condición especial registrada |
| RESERV | low | Reserva registrada |
| LIMITACIONES | medium | Limitaciones al dominio |
| HABITACION FAMILIAR | medium | Habitación familiar constituida |
| bajo valor | low | Valor fiscal por debajo del promedio |
