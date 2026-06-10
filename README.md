# Consulta de Sociedades — Registro Nacional de Costa Rica

Script de línea de comandos que consulta el **nombre o razón social** de una
persona jurídica costarricense en el [Registro Nacional](https://www.rnpdigital.com)
(RNP), a partir de su **cédula jurídica**.

Además de la razón social, devuelve el estado actual de la entidad y las citas de
presentación cuando están disponibles.

## ¿Cómo funciona?

La consulta gratuita del RNP requiere una cuenta registrada e iniciar sesión. El
sitio permite **una sola sesión activa por usuario**: si ya hay una abierta (por
ejemplo, en tu navegador), el script la cierra automáticamente y crea una nueva.

Internamente el script:

1. Inicia sesión en `rnpdigital.com` (manejando los tokens JSF/A4J del formulario).
2. Si detecta el modal de "sesión activa", confirma para continuar y cerrar la otra sesión.
3. Abre el formulario de consulta de persona jurídica por cédula.
4. Parsea el resultado y lo imprime de forma legible.

No depende de librerías externas: usa solo la biblioteca estándar de Python.

## Requisitos

- **Python 3** (no requiere paquetes adicionales).
- Una **cuenta registrada** en [rnpdigital.com](https://www.rnpdigital.com).

## Uso

```bash
# Pasando la cédula como argumento (pedirá credenciales si no las da)
python3 rnp_consulta.py 3109766273

# Acepta la cédula con o sin guiones
python3 rnp_consulta.py 3-109-766273 --user correo@ejemplo.com --pass MiClave

# Usando variables de entorno para las credenciales
RNP_USER=correo@ejemplo.com RNP_PASS=MiClave python3 rnp_consulta.py 3109766273
```

Si no se indican, el script pedirá la cédula y las credenciales de forma interactiva
(la contraseña se solicita de forma oculta).

### Credenciales

Orden de prioridad para las credenciales:

1. Argumentos `--user` / `--pass`
2. Variables de entorno `$RNP_USER` / `$RNP_PASS`
3. Prompt interactivo

> **Recomendación:** usá variables de entorno o el prompt interactivo. Evitá pasar
> la contraseña con `--pass` en sistemas compartidos, ya que queda visible en el
> historial del shell y en la lista de procesos.

## Ejemplo de salida

```
• Iniciando sesión…
• Consultando 3-109-766273…

Cédula jurídica : 3-109-766273
Razón social    : EJEMPLO SOCIEDAD ANONIMA
Estado          : INSCRITA
Citas           : ...
```

## Formato de la cédula jurídica

La cédula jurídica debe tener **10 dígitos**. Se acepta con o sin guiones:

- `3109766273`
- `3-109-766273`

## Aviso

Este proyecto no está afiliado al Registro Nacional de Costa Rica. Es una
herramienta no oficial que automatiza la consulta pública disponible en el sitio
del RNP, sujeta a los términos de uso del sitio. Usalo de forma responsable.
