# Chatbox

MVP de chatbot para concesionaria orientado a **calificar consultas antes de derivarlas a ventas**.

## Objetivo

Reducir consultas improductivas, especialmente operaciones en las que el interesado no acepta realizar la transferencia de la unidad.

## Flujo MVP

1. Vehículo de interés.
2. Destino de la unidad: personal / tercero / reventa.
3. Titular de la transferencia.
4. Confirmación explícita de transferencia obligatoria.
5. Forma de pago.
6. Nombre y apellido.
7. Scoring interno y clasificación.

Estados:
- `IN_PROGRESS`: conversación en curso.
- `QUALIFIED`: lead apto para derivar a ventas.
- `REVIEW`: requiere revisión antes de derivar.
- `REJECTED`: no acepta la transferencia obligatoria.

> El scoring ayuda a priorizar/revisar. La regla determinante del MVP es la aceptación explícita de la transferencia.

## Ejecutar localmente

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Abrir `http://127.0.0.1:5000`.

## API

### Chat

`POST /api/chat`

```json
{
  "session_id": "cliente-001",
  "message": "Amarok 2021"
}
```

### Leads

`GET /api/leads`

### Reiniciar prueba

`POST /api/reset/<session_id>`

## Próximas etapas

- Ajustar preguntas con el proceso real de la concesionaria.
- Crear panel de leads para vendedores.
- Incorporar detección de frases de riesgo como “sin transferir” o “precio reventa”.
- Conectar el webhook con la API oficial de WhatsApp Business/Cloud API.
- Notificar al vendedor cuando un lead queda `QUALIFIED`.
- Agregar pruebas automáticas de los flujos principales.

La interfaz incluida es un simulador para validar el flujo antes de conectar WhatsApp real.
