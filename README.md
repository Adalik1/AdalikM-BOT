# 💎 AdalikM-Bot

> *Sistema automatizado de distribución segura de archivos mediante claves de un solo uso*
> **Desarrollado por Adalik**

---

## 📖 Descripción general

**AdalikM-Bot** es un bot de Telegram diseñado para recibir archivos `.txt`, almacenarlos en un entorno seguro y generar una **clave de descarga única y temporal (24 h)**.
Cualquier usuario con la clave puede recuperar el archivo una sola vez utilizando el comando `/get <clave>`.

---

## 🚀 Características principales

* 🔐 **Claves de un solo uso**
  Cada archivo genera una clave irrepetible y se marca como usada tras la descarga.

* ⏰ **Expiración automática**
  Las claves expiran después del tiempo configurado (`EXPIRY_HOURS`, por defecto 24 h).

* 💾 **Almacenamiento persistente**
  Los archivos se guardan tanto en disco (`/data/storage`) como en la base de datos SQLite (`AdalikM.db`).

* ⚙️ **Gestión con Docker Compose**
  Preparado para despliegue 24/7 con reinicios automáticos.

* 📦 **Autopurga de archivos usados o vencidos**
  Limpieza periódica controlada por `AUTO_PURGE_INTERVAL`.

---

## 🧩 Estructura del proyecto

```
ADALIKM-BOT/
├── data/
│   ├── storage/           # Archivos subidos por los usuarios
│   └── AdalikM.db         # Base de datos SQLite
├── bot.py                 # Lógica principal del bot
├── Dockerfile             # Imagen de construcción del contenedor
├── docker-compose.yml     # Configuración de despliegue
├── .env                   # Variables de entorno (no se sube a Git)
├── .env.example           # Plantilla de referencia para el .env
└── README.md              # Este documento
```

---

## ⚙️ Instalación y configuración

### 1️⃣ Requisitos previos

* Ubuntu 20.04 / 22.04 (recomendado)
* Docker y Docker Compose instalados
* Un token de bot válido de [@BotFather](https://t.me/BotFather)

```bash
apt update && apt install -y docker.io docker-compose-plugin
```

---

### 2️⃣ Clonar el repositorio

```bash
git clone https://github.com/<tu_usuario>/adalikm-bot.git
cd adalikm-bot
```

---

### 3️⃣ Crear el archivo `.env`

Copia el ejemplo y ajusta tus valores:

```bash
cp .env.example .env
nano .env
```

Ejemplo de contenido:

```env
BOT_TOKEN=7256478866:AAFKnOb0lI8Irl-O90IS1hsDLlRs66XkoM0
EXPIRY_HOURS=24
AUTH_FORWARDERS=
ALLOWED_UPLOADERS=
MAX_BYTES=2000000
MIN_INTERVAL=1.0
AUTO_PURGE_INTERVAL=3600
DB_PATH=/data/AdalikM.db
STORAGE_DIR=/data/storage
PYTHONUNBUFFERED=1
```

Guarda con `Ctrl + O`, luego `Ctrl + X`.

---

### 4️⃣ Levantar el bot

```bash
docker compose up -d --build
```

Para revisar logs en vivo:

```bash
docker compose logs -f adalikm
```

Detener el servicio:

```bash
docker compose down
```

---

## 💬 Comandos disponibles

| Comando           | Descripción                                  |
| ----------------- | -------------------------------------------- |
| `/start`          | Muestra el mensaje de bienvenida.            |
| `/help`           | Lista de comandos disponibles.               |
| `/id`             | Devuelve tu identificador de usuario.        |
| `/ping`           | Comprobación de estado del bot.              |
| `/get <clave>`    | Descarga un archivo mediante clave.          |
| `/status <clave>` | Consulta el tiempo de vigencia de una clave. |

---

## 🧠 Funcionamiento interno

1. El usuario envía un archivo `.txt`.
2. El bot valida tamaño, extensión y duplicados.
3. Se genera una **clave única** (hash SHA-256).
4. Se guarda el archivo en `/data/storage` y la referencia en la base de datos.
5. El usuario recibe la clave y las instrucciones.
6. Otro usuario usa `/get <clave>` → descarga una sola vez.
7. Pasadas 24 h, el archivo se elimina automáticamente.

---

## 🛡️ Seguridad

* Claves imposibles de adivinar (`secrets.token_hex` + `SHA-256`).
* Control de tamaño (`MAX_BYTES`) para evitar abusos.
* Límite de solicitudes por usuario (`MIN_INTERVAL`).
* Eliminación programada de archivos vencidos o usados.
* Soporte opcional de lista blanca (`ALLOWED_UPLOADERS`) y reenvíos autorizados (`AUTH_FORWARDERS`).

---

## 🧰 Mantenimiento útil

| Tarea                         | Comando                                                             |
| ----------------------------- | ------------------------------------------------------------------- |
| Ver contenedores activos      | `docker ps`                                                         |
| Ver logs                      | `docker compose logs -f adalikm`                                    |
| Forzar limpieza de expirados  | Ejecutar `purge_expired_and_used()` manualmente o esperar el ciclo. |
| Otorgar permisos de escritura | `chmod -R 777 data`                                                 |
| Reiniciar contenedor          | `docker compose restart adalikm`                                    |

---

## 🌍 Despliegue en producción (Contabo VPS S)

1. Conéctate por SSH:

   ```bash
   ssh root@<tu_ip>
   ```
2. Instala dependencias y clona el repo.
3. Crea el `.env` con tu token.
4. Levanta con Docker Compose:

   ```bash
   docker compose up -d --build
   ```
5. Verifica logs:

   ```bash
   docker compose logs -f adalikm
   ```

---

## 🧾 Licencia y créditos

Proyecto desarrollado por **Adalik**
Distribuido bajo licencia privada de uso interno.
© 2025 Todos los derechos reservados.
