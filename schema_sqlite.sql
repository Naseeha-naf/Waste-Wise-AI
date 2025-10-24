PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS Institutions (
    inst_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS Locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inst_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (inst_id) REFERENCES Institutions(inst_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Waste_Records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    plastic_kg REAL NOT NULL CHECK(plastic_kg >= 0),
    organic_kg REAL NOT NULL CHECK(organic_kg >= 0),
    record_date DATE NOT NULL,
    FOREIGN KEY (location_id) REFERENCES Locations(location_id) ON DELETE CASCADE
);
