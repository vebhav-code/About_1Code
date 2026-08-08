-- Migration: Add site_visits table for anonymous landing page daily traffic stats
CREATE TABLE IF NOT EXISTS site_visits (
    visit_date DATE PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);
