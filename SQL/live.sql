use sacstrsx_24071256;

show tables;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    firstname VARCHAR(50) not null,
    lastname VARCHAR(50) not null,
    email VARCHAR(100) UNIQUE,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(255),
    status tinyint DEFAULT 0,
    role enum('user','admin') default 'user'
);
SET FOREIGN_KEY_CHECKS = 0;
truncate table users;
SET FOREIGN_KEY_CHECKS = 1;
select * from users;
UPDATE users
SET role = 'admin'
WHERE id = 2;

-- adding the two new column in the user table
ALTER TABLE users
ADD COLUMN reset_code VARCHAR(4),
ADD COLUMN reset_expiry DATETIME;

-- creating the profile for the user
CREATE TABLE user_profile (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    fullname VARCHAR(255),
    profile_picture VARCHAR(255)
) ENGINE=InnoDB;
select * from user_profile;

-- displaying

create table hotels(
	hotel_id int primary key auto_increment,
    hotel_name varchar(100) not null,
    location varchar(200) not null
);
select * from hotels;


create table rooms(
	room_id int primary key auto_increment,
    hotel_id int not null,
    room_name varchar(100) not null,
    room_count int not null default 0,
    price decimal(10,2) not null,
    peak_season decimal (10,2) not null,
    images varchar(100) not null,
    status VARCHAR(50) DEFAULT 'Available',
    foreign key(hotel_id) references hotels(hotel_id)
);
select * from rooms;


create table booking(
	booking_id int primary key auto_increment,
    room_id int not null,
    customer_name varchar(100) not null,
    user_id INT NOT NULL,
    check_in datetime not null,
    check_out datetime not null,
    booking_date datetime default current_timestamp,
    foreign key (room_id) references rooms(room_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
select * from booking;

-- creating the table cancellation
CREATE TABLE booking_cancellations (
    cancellation_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    user_id INT NOT NULL,
    cancellation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    days_before_checkin INT NOT NULL,
    booking_amount DECIMAL(10,2) NOT NULL,
    cancellation_charge DECIMAL(10,2) NOT NULL,
    refund_amount DECIMAL(10,2) NOT NULL,
    cancellation_reason TEXT NOT NULL,
    cancelled_by_admin BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;
select * from booking_cancellations;

CREATE TABLE exchange_rates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    currency VARCHAR(10) NOT NULL UNIQUE,
    rate DECIMAL(10, 2) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_currency (currency)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- inserting default exchange rates
INSERT INTO exchange_rates (currency, rate) VALUES
('USD', 1.27),
('NPR', 171.50),
('AUD', 1.93),
('INR', 106.50);

select * from exchange_rates;

CREATE TABLE IF NOT EXISTS booking_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rule_name VARCHAR(50) NOT NULL UNIQUE,
    rule_value INT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_rule_name (rule_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default booking rules
INSERT INTO booking_rules (rule_name, rule_value) VALUES
('max_booking_days', 30),      -- Maximum 30 days per booking
('max_advance_days', 90)       -- Can book up to 90 days (3 months) in advance
ON DUPLICATE KEY UPDATE rule_value = VALUES(rule_value);

-- View the data
SELECT * FROM booking_rules;


insert into hotels(hotel_name,location)
values('World Hotel','Aberdeen'),
('World Hotel','Belfast'),
('World Hotel','Birmingham'),
('World Hotel','Bournemouth'),
('World Hotel','Bristol'),
('World Hotel','Cardiff'),
('World Hotel','Edinburgh'),
('World Hotel','Glasgow'),
('World Hotel','Kent'),
('World Hotel','London'),
('World Hotel','Manchester'),
('World Hotel','Newcastle'),
('World Hotel','Norwich'),
('World Hotel','Nottingham'),
('World Hotel','Oxford'),
('World Hotel','Plymouth'),
('World Hotel','Swansea');

-- 1 Aberdeen (off-peak standard = 70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(1,'Standard Room',27,70,140,'images/single1.jpg'),
(1,'Double Room',45,84,168,'images/double1.jpg'),
(1,'Family Room',18,105,210,'images/family1.jpg');

-- 2 Belfast (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(2,'Standard Room',24,70,130,'images/single2.jpg'),
(2,'Double Room',40,84,156,'images/double2.jpg'),
(2,'Family Room',16,105,195,'images/family2.jpg');

-- 3 Birmingham (75)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(3,'Standard Room',33,75,150,'images/single3.jpg'),
(3,'Double Room',55,90,180,'images/double3.jpg'),
(3,'Family Room',22,113,225,'images/family3.jpg');

-- 4 Bristol (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(4,'Standard Room',30,70,140,'images/single4.jpg'),
(4,'Double Room',50,84,168,'images/double4.jpg'),
(4,'Family Room',20,105,210,'images/family4.jpg');

-- 5 Cardiff (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(5,'Standard Room',27,70,130,'images/single5.jpg'),
(5,'Double Room',45,84,156,'images/double5.jpg'),
(5,'Family Room',18,105,195,'images/family5.webp');

-- 6 Edinburgh (80)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(6,'Standard Room',36,80,160,'images/single7.jpg'),
(6,'Double Room',60,96,192,'images/double7.jpg'),
(6,'Family Room',24,120,240,'images/family7.jpg');

-- 7 Glasgow (75)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(7,'Standard Room',42,75,150,'images/single8.jpg'),
(7,'Double Room',70,90,180,'images/double8.jpg'),
(7,'Family Room',28,113,225,'images/family8.jpg');

-- 8 London (100)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(8,'Standard Room',48,100,200,'images/single9.jpg'),
(8,'Double Room',80,120,240,'images/double9.jpg'),
(8,'Family Room',32,150,300,'images/family9.jpg');

-- 9 Manchester (90)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(9,'Standard Room',45,90,180,'images/single8.jpg'),
(9,'Double Room',75,108,216,'images/single8.jpg'),
(9,'Family Room',30,135,270,'images/single8.jpg');

-- 10 Newcastle (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(10,'Standard Room',27,70,120,'images/single1.jpg'),
(10,'Double Room',45,84,144,'images/double1.jpg'),
(10,'Family Room',18,105,180,'images/family100.jpg');

-- 11 Norwich (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(11,'Standard Room',27,70,130,'images/single100.jpg'),
(11,'Double Room',45,84,156,'images/double100.jpg'),
(11,'Family Room',18,105,195,'images/family100.jpg');

-- 12 Nottingham (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(12,'Standard Room',33,70,130,'images/single99.jpg'),
(12,'Double Room',55,84,156,'images/double99.jpg'),
(12,'Family Room',22,105,195,'images/family99.jpg');

-- 13 Oxford (90)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(13,'Standard Room',27,90,180,'images/single4.jpg'),
(13,'Double Room',45,108,216,'images/double4.jpg'),
(13,'Family Room',18,135,270,'images/family4.jpg');

-- 14 Plymouth (90)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(14,'Standard Room',24,90,180,'images/single5.jpg'),
(14,'Double Room',40,108,216,'images/double5.jpg'),
(14,'Family Room',16,135,270,'images/family5.jpg');

-- 15 Swansea (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(15,'Standard Room',21,70,130,'images/single9.jpg'),
(15,'Double Room',35,84,156,'images/double9.jpg'),
(15,'Family Room',14,105,195,'images/family9.jpg');

-- 16 Bournemouth (70)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(16,'Standard Room',27,70,130,'images/single4.jpg'),
(16,'Double Room',45,84,156,'images/single4.jpg'),
(16,'Family Room',18,105,195,'images/single4.jpg');

-- 17 Kent (80)
insert into rooms (hotel_id,room_name,room_count,price,peak_season,images) values
(17,'Standard Room',30,80,140,'images/single1.jpg'),
(17,'Double Room',50,96,168,'images/double2.jpg'),
(17,'Family Room',20,120,210,'images/family2.jpg');