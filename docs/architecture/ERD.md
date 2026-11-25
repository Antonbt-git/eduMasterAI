# ERD — EduMaster.ai (resumen)

```mermaid
erDiagram
  Organization ||--o{ User : has
  Organization ||--o{ Course : owns
  Organization ||--o{ ModelRun : scopes
  Organization ||--o{ ModelVersion : scopes
  User ||--o| Student : is
  Student ||--o{ Enrollment : has
  Course ||--o{ Enrollment : has
  Student ||--o{ LearningEvent : generates
  Student ||--o{ Prediction : receives
  ModelRun ||--o{ ModelVersion : produces
  Student ||--o{ Certificate : earns
  Course ||--o{ Certificate : certifies
```

## Multi-tenant
`ModelRun` y `ModelVersion` llevan `organization_id` nullable: `NULL` = artefacto de
plataforma (DEMO/bootstrap), visible para todas las instituciones; con valor = aislado
por institución. Superadmin ve todo.
