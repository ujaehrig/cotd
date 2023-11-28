-- Text encoding used: UTF-8
-- Table: user
CREATE TABLE IF NOT EXISTS user (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
        weekdays varchar(10),	
	mail varchar (50) UNIQUE NOT NULL, 
	last_chosen date,
        vacation_start DATE,
        vacation_end   DATE
);

