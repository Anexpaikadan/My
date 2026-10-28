/* Valley MMA Fight Club – sample data for testing (dates are relative to the day you import it). */
/* Sample member login: phone 9847012345, password member123 */

INSERT INTO members (id, adm_no, name, phone, gender, place, city, district, post, pin_code, state, occupation, dob, age, height_cm, weight_kg, blood_group, bmi, hq1, hq2, hq3, hq4, hq5, hq6, hq7, hq8, declaration, trainer_name, join_date, plan_id, start_date, expiry_date, password_hash, card_token) VALUES
  (1, 'VM001', 'Muhammed Shafi', '9847012345', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Student', '1998-04-12', 28, 175, 72, 'B+', 23.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 200 DAY, 1, CURDATE() - INTERVAL 10 DAY, CURDATE() + INTERVAL 20 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '15196325a32fe8de'),
  (2, 'VM002', 'Arjun Krishnan', '9895123456', 'M', 'Manjeri', 'Manjeri', 'Malappuram', 'Manjeri', '676521', 'Kerala', 'Engineer', '1995-09-03', 31, 170, 68, 'O+', 23.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 180 DAY, 2, CURDATE() - INTERVAL 87 DAY, CURDATE() + INTERVAL 3 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '6e37d8de303e450c'),
  (3, 'VM003', 'Fathima Rinsha', '9744234567', 'F', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Teacher', '2001-01-20', 25, 160, 55, 'A+', 21.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 95 DAY, 1, CURDATE() - INTERVAL 35 DAY, CURDATE() - INTERVAL 5 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '7e25994dddaa9ca0'),
  (4, 'VM004', 'Rahul Das', '9605345678', 'M', 'Wandoor', 'Wandoor', 'Malappuram', 'Wandoor', '676521', 'Kerala', 'Driver', '1993-07-15', 33, 178, 80, 'AB+', 25.2, 0,0,0,1,0,0,0,1, 1, 'Coach Anees', CURDATE() - INTERVAL 62 DAY, 3, CURDATE() - INTERVAL 62 DAY, CURDATE() + INTERVAL 120 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '0a605956ca2e1738'),
  (5, 'VM005', 'Ajmal P', '9562456789', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Business', '1997-11-30', 29, 172, 74, 'B-', 25, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 400 DAY, 4, CURDATE() - INTERVAL 115 DAY, CURDATE() + INTERVAL 250 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '88afdef230f754c4'),
  (6, 'VM006', 'Nihal K', '9946567890', 'M', 'Melattur', 'Melattur', 'Malappuram', 'Melattur', '676521', 'Kerala', 'Student', '2004-03-08', 22, 168, 61, 'O-', 21.6, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 29 DAY, 1, CURDATE() - INTERVAL 29 DAY, CURDATE() + INTERVAL 1 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '0300f03d052a13dc'),
  (7, 'VM007', 'Anjali Menon', '9037678901', 'F', 'Perinthalmanna', 'Perinthalmanna', 'Malappuram', 'Perinthalmanna', '676521', 'Kerala', 'Nurse', '1999-06-25', 27, 158, 52, 'A-', 20.8, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 120 DAY, 2, CURDATE() - INTERVAL 120 DAY, CURDATE() - INTERVAL 30 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '4c599ba2293abf02'),
  (8, 'VM008', 'Shahid Ali', '8086789012', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Electrician', '2000-12-01', 26, 174, 77, 'B+', 25.4, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 15 DAY, 1, CURDATE() - INTERVAL 15 DAY, CURDATE() + INTERVAL 15 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '37c92bff142ea3ee'),
  (9, 'VM009', 'Vishnu Prasad', '7012890123', 'M', 'Karuvarakundu', 'Karuvarakundu', 'Malappuram', 'Karuvarakundu', '676521', 'Kerala', 'Police', '1996-02-14', 30, 180, 85, 'O+', 26.2, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 150 DAY, 1, CURDATE() - INTERVAL 24 DAY, CURDATE() + INTERVAL 6 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '89ede8e708770d57'),
  (10, 'VM010', 'Sanju Thomas', '9446901234', 'M', 'Nilambur', 'Nilambur', 'Malappuram', 'Nilambur', '676521', 'Kerala', 'Shop owner', '1994-10-10', 32, 169, 70, 'A+', 24.5, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 90 DAY, 1, CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 60 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '70d8a703575d7e6b'),
  (11, 'VM011', 'Adil Rahman', '8129012345', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', 'Pandikkad', '676521', 'Kerala', 'Student', '2006-05-05', 20, 165, 58, 'B+', 21.3, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 20 DAY, 2, CURDATE() - INTERVAL 20 DAY, CURDATE() + INTERVAL 70 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '7924413444a02ac3'),
  (12, 'VM012', 'Sneha Raj', '9539123456', 'F', 'Manjeri', 'Manjeri', 'Malappuram', 'Manjeri', '676521', 'Kerala', 'Accountant', '2002-08-18', 24, 162, 57, 'O+', 21.7, 0,0,0,0,0,0,0,0, 1, 'Coach Anees', CURDATE() - INTERVAL 2 DAY, 1, CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 28 DAY, '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', '4214737ce705c7a7');

INSERT INTO payments (receipt_no, member_id, plan_id, pay_date, admission_fee, plan_fee, other_fee, other_note, total, paid, method, upi_ref, period_start, period_end, note) VALUES
  (1001, 1, 1, CURDATE() - INTERVAL 10 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 10 DAY, CURDATE() + INTERVAL 20 DAY, ''),
  (1002, 2, 2, CURDATE() - INTERVAL 87 DAY, 0, 4000, 0, '', 4000, 4000, 'upi', 'UPI4002', CURDATE() - INTERVAL 87 DAY, CURDATE() + INTERVAL 3 DAY, ''),
  (1003, 3, 1, CURDATE() - INTERVAL 35 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 35 DAY, CURDATE() - INTERVAL 5 DAY, ''),
  (1004, 4, 3, CURDATE() - INTERVAL 62 DAY, 500, 7500, 0, '', 8000, 8000, 'upi', 'UPI4004', CURDATE() - INTERVAL 62 DAY, CURDATE() + INTERVAL 120 DAY, ''),
  (1005, 5, 4, CURDATE() - INTERVAL 115 DAY, 0, 14000, 0, '', 14000, 14000, 'cash', '', CURDATE() - INTERVAL 115 DAY, CURDATE() + INTERVAL 250 DAY, ''),
  (1006, 6, 1, CURDATE() - INTERVAL 29 DAY, 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4006', CURDATE() - INTERVAL 29 DAY, CURDATE() + INTERVAL 1 DAY, ''),
  (1007, 7, 2, CURDATE() - INTERVAL 120 DAY, 500, 4000, 0, '', 4500, 4500, 'cash', '', CURDATE() - INTERVAL 120 DAY, CURDATE() - INTERVAL 30 DAY, ''),
  (1008, 8, 1, CURDATE() - INTERVAL 15 DAY, 500, 1500, 0, '', 2000, 1000, 'upi', 'UPI4008', CURDATE() - INTERVAL 15 DAY, CURDATE() + INTERVAL 15 DAY, ''),
  (1009, 9, 1, CURDATE() - INTERVAL 24 DAY, 0, 1500, 0, '', 1500, 1500, 'cash', '', CURDATE() - INTERVAL 24 DAY, CURDATE() + INTERVAL 6 DAY, ''),
  (1010, 10, 1, CURDATE() - INTERVAL 90 DAY, 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4010', CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 60 DAY, ''),
  (1011, 11, 2, CURDATE() - INTERVAL 20 DAY, 500, 4000, 0, '', 4500, 4500, 'cash', '', CURDATE() - INTERVAL 20 DAY, CURDATE() + INTERVAL 70 DAY, ''),
  (1012, 12, 1, CURDATE(), 500, 1500, 0, '', 2000, 2000, 'upi', 'UPI4012', CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 28 DAY, ''),
  (1013, 1, NULL, CURDATE(), 0, 0, 300, 'Gloves', 300, 300, 'upi', 'UPI4999', NULL, NULL, 'Boxing gloves'),
  (1014, 8, NULL, CURDATE(), 0, 0, 0, '', 0, 500, 'cash', '', NULL, NULL, 'Balance payment');

INSERT IGNORE INTO attendance (member_id, att_date, check_in, method) VALUES
  (1, CURDATE() - INTERVAL 1 DAY, '07:34:00', 'qr'),
  (1, CURDATE(), '18:47:00', 'card'),
  (2, CURDATE() - INTERVAL 3 DAY, '19:15:00', 'manual'),
  (2, CURDATE() - INTERVAL 2 DAY, '08:28:00', 'qr'),
  (2, CURDATE(), '08:54:00', 'manual'),
  (3, CURDATE() - INTERVAL 6 DAY, '17:43:00', 'qr'),
  (3, CURDATE() - INTERVAL 5 DAY, '06:56:00', 'card'),
  (4, CURDATE() - INTERVAL 8 DAY, '07:24:00', 'manual'),
  (4, CURDATE() - INTERVAL 7 DAY, '18:37:00', 'qr'),
  (4, CURDATE() - INTERVAL 5 DAY, '18:03:00', 'manual'),
  (4, CURDATE() - INTERVAL 4 DAY, '07:16:00', 'qr'),
  (4, CURDATE() - INTERVAL 3 DAY, '18:29:00', 'card'),
  (4, CURDATE() - INTERVAL 1 DAY, '18:55:00', 'qr'),
  (4, CURDATE(), '07:08:00', 'card'),
  (5, CURDATE() - INTERVAL 10 DAY, '19:05:00', 'card'),
  (5, CURDATE() - INTERVAL 9 DAY, '08:18:00', 'manual'),
  (5, CURDATE() - INTERVAL 7 DAY, '08:44:00', 'card'),
  (5, CURDATE() - INTERVAL 6 DAY, '19:57:00', 'manual'),
  (5, CURDATE() - INTERVAL 4 DAY, '19:23:00', 'card'),
  (5, CURDATE() - INTERVAL 3 DAY, '08:36:00', 'manual'),
  (5, CURDATE() - INTERVAL 2 DAY, '19:49:00', 'qr'),
  (5, CURDATE(), '19:15:00', 'manual'),
  (6, CURDATE() - INTERVAL 13 DAY, '17:-27:00', 'manual'),
  (6, CURDATE() - INTERVAL 12 DAY, '06:-14:00', 'qr'),
  (6, CURDATE() - INTERVAL 11 DAY, '17:-1:00', 'card'),
  (6, CURDATE() - INTERVAL 9 DAY, '17:25:00', 'qr'),
  (6, CURDATE() - INTERVAL 8 DAY, '06:38:00', 'card'),
  (6, CURDATE() - INTERVAL 6 DAY, '06:04:00', 'qr'),
  (6, CURDATE() - INTERVAL 5 DAY, '17:17:00', 'card'),
  (6, CURDATE() - INTERVAL 3 DAY, '17:43:00', 'qr'),
  (6, CURDATE() - INTERVAL 2 DAY, '06:56:00', 'card'),
  (6, CURDATE() - INTERVAL 1 DAY, '17:09:00', 'manual'),
  (8, CURDATE() - INTERVAL 14 DAY, '08:-26:00', 'qr'),
  (8, CURDATE() - INTERVAL 13 DAY, '19:-13:00', 'card'),
  (8, CURDATE() - INTERVAL 11 DAY, '19:13:00', 'qr'),
  (8, CURDATE() - INTERVAL 10 DAY, '08:26:00', 'card'),
  (8, CURDATE() - INTERVAL 9 DAY, '19:39:00', 'manual'),
  (8, CURDATE() - INTERVAL 7 DAY, '19:05:00', 'card'),
  (8, CURDATE() - INTERVAL 6 DAY, '08:18:00', 'manual'),
  (8, CURDATE() - INTERVAL 4 DAY, '08:44:00', 'card'),
  (8, CURDATE() - INTERVAL 3 DAY, '19:57:00', 'manual'),
  (8, CURDATE() - INTERVAL 1 DAY, '19:23:00', 'card'),
  (8, CURDATE(), '08:36:00', 'manual'),
  (9, CURDATE() - INTERVAL 20 DAY, '17:-37:00', 'card'),
  (9, CURDATE() - INTERVAL 19 DAY, '06:-24:00', 'manual'),
  (9, CURDATE() - INTERVAL 18 DAY, '17:-11:00', 'qr'),
  (9, CURDATE() - INTERVAL 16 DAY, '17:-45:00', 'manual'),
  (9, CURDATE() - INTERVAL 15 DAY, '06:-32:00', 'qr'),
  (9, CURDATE() - INTERVAL 13 DAY, '06:-6:00', 'manual'),
  (9, CURDATE() - INTERVAL 12 DAY, '17:07:00', 'qr'),
  (9, CURDATE() - INTERVAL 10 DAY, '17:33:00', 'manual'),
  (9, CURDATE() - INTERVAL 9 DAY, '06:46:00', 'qr'),
  (9, CURDATE() - INTERVAL 8 DAY, '17:59:00', 'card'),
  (9, CURDATE() - INTERVAL 6 DAY, '17:25:00', 'qr'),
  (9, CURDATE() - INTERVAL 5 DAY, '06:38:00', 'card'),
  (9, CURDATE() - INTERVAL 3 DAY, '06:04:00', 'qr'),
  (9, CURDATE() - INTERVAL 2 DAY, '17:17:00', 'card'),
  (9, CURDATE(), '17:43:00', 'qr'),
  (11, CURDATE() - INTERVAL 20 DAY, '19:-23:00', 'qr'),
  (11, CURDATE() - INTERVAL 18 DAY, '19:-57:00', 'manual'),
  (11, CURDATE() - INTERVAL 17 DAY, '08:-44:00', 'qr'),
  (11, CURDATE() - INTERVAL 16 DAY, '19:-31:00', 'card'),
  (11, CURDATE() - INTERVAL 14 DAY, '19:-5:00', 'qr'),
  (11, CURDATE() - INTERVAL 13 DAY, '08:08:00', 'card'),
  (11, CURDATE() - INTERVAL 11 DAY, '08:34:00', 'qr'),
  (11, CURDATE() - INTERVAL 10 DAY, '19:47:00', 'card'),
  (11, CURDATE() - INTERVAL 8 DAY, '19:13:00', 'qr'),
  (11, CURDATE() - INTERVAL 7 DAY, '08:26:00', 'card'),
  (11, CURDATE() - INTERVAL 6 DAY, '19:39:00', 'manual'),
  (11, CURDATE() - INTERVAL 4 DAY, '19:05:00', 'card'),
  (11, CURDATE() - INTERVAL 3 DAY, '08:18:00', 'manual'),
  (11, CURDATE() - INTERVAL 1 DAY, '08:44:00', 'card'),
  (11, CURDATE(), '19:57:00', 'manual'),
  (12, CURDATE() - INTERVAL 2 DAY, '06:38:00', 'card'),
  (12, CURDATE(), '06:04:00', 'qr');

/* Accounts: opening balances and some income / expense entries */
UPDATE acc_accounts SET opening_balance = 5000 WHERE id = 1;
UPDATE acc_accounts SET opening_balance = 20000 WHERE id = 2;
INSERT INTO acc_entries (voucher_no, entry_date, type, category_id, account_id, to_account_id, amount, party, description, ref_no) VALUES
  (1, CURDATE() - INTERVAL 25 DAY, 'expense', 20, 2, NULL, 12000, 'Building owner', 'Gym hall rent', 'UPI8812'),
  (2, CURDATE() - INTERVAL 20 DAY, 'expense', 21, 1, NULL, 2350, 'KSEB', 'Electricity bill', ''),
  (3, CURDATE() - INTERVAL 18 DAY, 'expense', 25, 2, NULL, 4800, 'Sports shop Manjeri', '2 punching bags', 'INV-221'),
  (4, CURDATE() - INTERVAL 15 DAY, 'income', 2, 1, NULL, 3000, 'Rahul Das', 'Personal training – 10 sessions', ''),
  (5, CURDATE() - INTERVAL 12 DAY, 'expense', 27, 1, NULL, 600, 'Cleaner', 'Cleaning – 2 weeks', ''),
  (6, CURDATE() - INTERVAL 10 DAY, 'transfer', NULL, 1, 2, 5000, '', 'Cash deposited in bank', ''),
  (7, CURDATE() - INTERVAL 5 DAY, 'income', 3, 1, NULL, 1200, 'Adil Rahman', 'Gloves and hand wraps', ''),
  (8, CURDATE() - INTERVAL 3 DAY, 'expense', 28, 2, NULL, 799, 'Jio', 'Internet', ''),
  (9, CURDATE() - INTERVAL 1 DAY, 'expense', 23, 2, NULL, 15000, 'Coach Anees', 'Trainer salary', 'UPI9921'),
  (10, CURDATE(), 'expense', 31, 1, NULL, 250, 'Shop', 'Drinking water cans', '');

/* A member with a birthday today, for the dashboard */
UPDATE members SET dob = CONCAT('2002-', DATE_FORMAT(CURDATE(), '%m-%d')) WHERE id = 12 AND DATE_FORMAT(CURDATE(), '%m-%d') <> '02-29';

/* An invited member who filled the join form (waiting for approval) and a deactivated member */
INSERT INTO members (id, adm_no, name, phone, gender, place, city, district, pin_code, state, occupation, dob, age, height_cm, weight_kg, bmi,
  hq1, hq2, hq3, hq4, hq5, hq6, hq7, hq8, declaration, join_date, password_hash, card_token, status, invite_token, details_at) VALUES
  (13, 'VM013', 'Faisal Babu', '9645012399', 'M', 'Pandikkad', 'Pandikkad', 'Malappuram', '676521', 'Kerala', 'Student', '2005-02-10', 21, 171, 64, 21.9,
   0, 0, 0, 0, 0, 0, 0, 0, 1, CURDATE(), '$2y$10$t8f22Rd9D9sitzXy8lB35.kpmUrwbobDSsyu5EooKtNkbK6/GSEFy', 'a1b2c3d4e5f60713', 'pending', 'c0ffee00c0ffee00c0ffee00c0ffee13', NOW());
UPDATE members SET status = 'inactive', notes = 'Deactivated: stopped coming' WHERE id = 10;

/* Gym leave and a member freeze */
INSERT INTO gym_leaves (from_date, to_date, title, message) VALUES
  (CURDATE() + INTERVAL 5 DAY, CURDATE() + INTERVAL 6 DAY, 'Festival holiday', 'Gym will be closed for the festival. Classes start again the next day as usual.');
INSERT INTO member_freezes (member_id, from_date, to_date, days, extended, reason, note) VALUES
  (4, CURDATE() - INTERVAL 3 DAY, CURDATE() + INTERVAL 4 DAY, 8, 1, 'injury', 'Knee injury, doctor rest');

/* Positions from attendance */
UPDATE members m SET level_id = (SELECT l.id FROM levels l WHERE l.from_day <= GREATEST(1, (SELECT COUNT(*) FROM attendance a WHERE a.member_id = m.id))
  ORDER BY l.from_day DESC LIMIT 1), level_since = CURDATE() WHERE m.level_auto = 1;

/* Complaints */
INSERT INTO complaints (id, member_id, category, subject, status, admin_unread, member_unread, created_at, updated_at) VALUES
  (1, 2, 'equipment', 'Punching bag chain is loose', 'progress', 0, 1, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY),
  (2, 8, 'timing', 'Morning batch at 6 am please', 'open', 1, 0, NOW() - INTERVAL 3 HOUR, NOW() - INTERVAL 3 HOUR);
INSERT INTO complaint_msgs (complaint_id, by_admin, message, created_at) VALUES
  (1, 0, 'The chain of the big punching bag near the window is loose and makes noise.', NOW() - INTERVAL 2 DAY),
  (1, 1, 'Thank you, we have ordered a new chain. It will be fixed this week.', NOW() - INTERVAL 1 DAY),
  (2, 0, 'Can we have a 6 am batch? 7 am is late for people going to work.', NOW() - INTERVAL 3 HOUR);
