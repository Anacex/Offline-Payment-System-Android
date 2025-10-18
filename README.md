# Offline Payment System Backend

A FastAPI-based backend for an offline payment system, using Docker and PostgreSQL.

## Features

- User management (create, list)
- Transaction management (create, list)
- Role-based user model (`payer`, `merchant`, `admin`)
- Interactive API docs via Swagger UI
- Dockerized for easy setup and deployment

## Project Structure

backend/
├── app/
│ ├── api/
│ │ └── v1/
│ │ ├── user.py
│ │ ├── transaction.py
│ │ └── health.py
│ ├── core/
│ │ ├── config.py
│ │ └── db.py
│ ├── models/
│ │ ├── base.py
│ │ ├── user.py
│ │ └── transaction.py
│ ├── main.py
│ └── init_db.py
├── tests/
│ └── test_user.py
│ └── test_transaction.py
├── docker-compose.yml
├── Dockerfile
└── README.md

text

## Getting Started

### Prerequisites

- Docker & Docker Compose installed

### Setup

1. **Build and start containers:**
docker-compose up -d

text

2. **Initialize the database:**
docker-compose run --rm web python -m app.init_db

text

3. **Access API docs:**
- Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

### Usage

- **Create a user:**  
`POST /users/`  
Example JSON:
{
"name": "Alice",
"email": "alice@example.com",
"role": "payer"
}

text

- **Create a transaction:**  
`POST /transactions/`  
Example JSON:
{
"from_user_id": 1,
"to_user_id": 2,
"amount": 50.0,
"token": "unique-token-123",
"sequence_number": 1
}

text

### Development Workflow

- **After code changes:**  
docker-compose build
docker-compose up -d

text

- **View logs:**  
docker-compose logs web

text

### Testing

- **Run unit tests:**  
pytest

text

## Troubleshooting

- If you get a `500 Internal Server Error`, check the backend logs for details.
- Always rebuild the Docker image after code changes.

## Contributing

- Follow the project structure for new endpoints.
- Write unit tests for new features.
- Document all API changes in this README.

---

**For further development:**  
- Add authentication and authorization.
- Implement offline sync logic.
- Integrate with frontend/mobile clients.
