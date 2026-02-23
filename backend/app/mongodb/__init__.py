"""
JanVedha MongoDB Module
=======================
Standalone MongoDB layer using Motor (async driver) + Beanie ODM.
This package is a drop-in replacement for the existing SQLAlchemy/SQLite layer.

Sub-packages:
  models/        — Beanie Document definitions (mirror of app/models/)
  repositories/  — Async CRUD data-access layer
  services/      — Business logic re-implemented for MongoDB

See README.md for integration instructions.
"""
