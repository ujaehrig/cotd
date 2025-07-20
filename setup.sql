-- Text encoding used: UTF-8
-- Table: user
CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        weekdays varchar(10),
        mail varchar (50) UNIQUE NOT NULL,
        last_chosen date,
        vacation_start DATE,
        vacation_end DATE
);
--
-- Update to include column ical
-- 
PRAGMA foreign_keys = 0;
CREATE TABLE user_temp_table AS
SELECT *
FROM user;
DROP TABLE user;
CREATE TABLE user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        weekdays VARCHAR (10),
        mail VARCHAR (50) UNIQUE NOT NULL,
        last_chosen DATE,
        vacation_start DATE,
        vacation_end DATE,
        ical VARCHAR (500)
);
INSERT INTO user (
                id,
                weekdays,
                mail,
                last_chosen,
                vacation_start,
                vacation_end
        )
SELECT id,
        weekdays,
        mail,
        last_chosen,
        vacation_start,
        vacation_end
FROM user_temp_table;
DROP TABLE user_temp_table;
PRAGMA foreign_keys = 1;