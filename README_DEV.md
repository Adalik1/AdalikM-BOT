# 🧑‍💻 README_DEV.md  
> _Guía de desarrollo local — AdalikM Bot (Adalik)_

---

## ⚙️ Descripción

Esta guía explica cómo desarrollar, probar y mantener **AdalikM Bot** desde **Windows 11**, utilizando **Docker Desktop** y **GitHub Desktop**.  
El objetivo es tener un entorno local estable, autorecargable y versionado correctamente, sin afectar la rama principal ni el entorno de producción.

---

## 🧩 Requisitos

| Requisito | Descripción |
|------------|-------------|
| 🪟 **Windows 11** | Sistema principal de desarrollo |
| 🐳 **Docker Desktop** | Con soporte para Docker Compose v2 |
| 🧰 **GitHub Desktop** | Control de versiones y commits locales |
| 💻 **Visual Studio Code** | Editor recomendado |
| 🐍 **Python 3.11+ (opcional)** | Solo si pruebas fuera de Docker |

---

## 📁 Estructura del proyecto

```

adalikm/
├── bot.py                    # Código principal del bot
├── Dockerfile                # Imagen base
├── docker-compose.yml        # Configuración de producción
├── docker-compose.dev.yml    # Configuración local (no subir)
├── data/                     # Archivos persistentes
├── .env                      # Variables locales (privado)
├── .env.example              # Plantilla
├── README.md                 # Doc. de producción
└── README_DEV.md             # Esta guía

````

---

## ⚙️ Variables de entorno (.env)

Crea un archivo `.env` en la raíz del proyecto:

```env
BOT_TOKEN=TU_TOKEN_DE_TELEGRAM
EXPIRY_HOURS=24
AUTH_FORWARDERS=
ALLOWED_UPLOADERS=
MAX_BYTES=2000000
MIN_INTERVAL=1.0
AUTO_PURGE_INTERVAL=3600
DB_PATH=/data/AdalikM.db
STORAGE_DIR=/data/storage
PYTHONUNBUFFERED=1
````

> ⚠️ **No subas este archivo a GitHub.**
> Agrega `.env` y `docker-compose.dev.yml` a tu `.gitignore`.

---

## 🧱 docker-compose.dev.yml

Archivo completo para desarrollo (no subir):

```yaml
version: "3.8"

services:
  adalikm:
    build: .
    container_name: adalikm-dev
    env_file:
      - .env
    environment:
      DB_PATH: /data/AdalikM.db
      STORAGE_DIR: /data/storage
      PYTHONUNBUFFERED: "1"
    volumes:
      - ./:/app          # Monta el código en vivo
      - ./data:/data     # Persistencia de DB y archivos
    working_dir: /app
    command: >
      bash -lc "
      pip install --no-cache-dir watchdog &&
      mkdir -p /data/storage &&
      watchmedo auto-restart --patterns='*.py' --recursive -- \
      python -u /app/bot.py
      "
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## ▶️ Cómo iniciar el entorno de desarrollo

1. Abre **Docker Desktop** → verifica que esté activo.
2. Abre **GitHub Desktop** → abre el repositorio local del bot.
3. En **VS Code** o terminal PowerShell dentro del proyecto, ejecuta:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Esto:

* Monta el código en vivo
* Crea la base de datos y almacenamiento
* Instala `watchdog`
* Reinicia automáticamente el bot al guardar (`Ctrl+S`)

---

## 🔍 Comandos rápidos

| Acción                   | Comando                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| Ver logs del bot         | `docker compose -f docker-compose.dev.yml logs -f`                                                        |
| Entrar al contenedor     | `docker compose -f docker-compose.dev.yml exec adalikm bash`                                              |
| Reiniciar el contenedor  | `docker compose -f docker-compose.dev.yml restart adalikm`                                                |
| Detener entorno          | `docker compose -f docker-compose.dev.yml down`                                                           |
| Reconstruir por completo | `docker compose -f docker-compose.dev.yml down -v && docker compose -f docker-compose.dev.yml up --build` |

---

## 🧪 Flujo de trabajo con GitHub Desktop

1. Abre tu proyecto en **GitHub Desktop**.
2. Crea una rama local para tus cambios (por ejemplo, `feature/ui-buttons`).
3. Realiza tus modificaciones en **VS Code**.
4. Docker reiniciará automáticamente el bot.
5. Comprueba los resultados en Telegram.
6. Haz *commit* de tus cambios (solo archivos de código).
7. Sube (*push*) la rama a GitHub para revisión o respaldo.

> ✅ Nunca incluyas `.env`, `data/`, `docker-compose.dev.yml` ni archivos temporales en los commits.

---

## 🧠 Depuración y mantenimiento

### Ver variables dentro del contenedor

```bash
docker compose -f docker-compose.dev.yml exec adalikm printenv | grep BOT_TOKEN
```

### Reasignar permisos en Windows

Si Docker no puede escribir en `/data`:

```bash
icacls data /grant Everyone:F /T
```

### Limpiar entorno

```bash
docker compose -f docker-compose.dev.yml down -v
```

---

## 🧩 Pruebas del bot

| Comando           | Descripción                   |
| ----------------- | ----------------------------- |
| `/start`          | Muestra mensaje de bienvenida |
| `/help`           | Lista de comandos             |
| `/id`             | Devuelve tu ID                |
| `/ping`           | Verifica estado               |
| `/get <clave>`    | Descarga archivo por clave    |
| `/status <clave>` | Consulta vigencia             |

---

## 🧾 Buenas prácticas

* 🚫 No subir archivos de entorno ni datos locales.
* 💾 Realizar commits solo del código fuente.
* 🧱 Mantener ramas `dev` y `main` limpias (sin config local).
* ✍️ Documentar nuevos endpoints o comandos en `README_DEV.md`.
* 🔄 Probar antes de hacer *merge* con la versión de producción (`docker-compose.yml`).

---

## 🧑‍💻 Créditos internos

**Proyecto:** AdalikM Bot
**Versión Dev:** 1.0.0
**Autor:** Adalik
**Stack:** Python 3.12 · aiosqlite · python-telegram-bot · Docker · GitHub Desktop