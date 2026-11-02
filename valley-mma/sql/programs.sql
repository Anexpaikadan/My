/* Programs on the public page (photo + details pop-up) and member achievements (public slider) */
CREATE TABLE IF NOT EXISTS programs (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  short_text VARCHAR(200) NOT NULL DEFAULT '',
  details TEXT NULL,
  suitable_for VARCHAR(150) NOT NULL DEFAULT '',
  schedule VARCHAR(200) NOT NULL DEFAULT '',
  trainer VARCHAR(100) NOT NULL DEFAULT '',
  trainer_about VARCHAR(300) NOT NULL DEFAULT '',
  /* assets/programs/… (standard photo) or media/programs/… (uploaded) */
  image VARCHAR(200) NOT NULL DEFAULT '',
  active TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  KEY idx_active (active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO programs (id, name, short_text, details, suitable_for, image, sort_order) VALUES
  (1, 'MMA', 'Striking, wrestling and ground work – the complete fight game',
   'Learn the complete fight game: punches and kicks, takedowns and wrestling, ground control and submissions.\nYou start with the basics and move up step by step – no experience needed.\nFor fighters: sparring and preparation for amateur and pro fights.',
   'Beginners and fighters, age 14+', 'assets/programs/mma.jpg', 1),
  (2, 'Boxing', 'Footwork, defence and powerful punches',
   'Stance, footwork and guard, the basic punches and combinations, defence (slip, block, roll) and counter punches.\nBag work, pad work with the coach and controlled sparring.',
   'Everyone, age 10+', 'assets/programs/boxing.jpg', 2),
  (3, 'Muay Thai', 'Kicks, knees, elbows and clinch work',
   'The art of eight limbs: kicks, knees, elbows, punches and clinch work.\nBuilds strong legs, balance, timing and great fitness.',
   'Beginners and fighters, age 12+', 'assets/programs/muaythai.jpg', 3),
  (4, 'Fitness', 'Strength, stamina and fat loss with fight conditioning',
   'Fight-style conditioning: circuits, bag rounds, bodyweight strength and core work.\nBurn fat, build stamina and get strong – without fighting.',
   'Everyone who wants to get fit', 'assets/programs/fitness.jpg', 4);

CREATE TABLE IF NOT EXISTS achievements (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  member_id INT UNSIGNED NULL,
  athlete VARCHAR(100) NOT NULL,
  title VARCHAR(150) NOT NULL,
  event VARCHAR(150) NOT NULL DEFAULT '',
  ach_date DATE NULL,
  details TEXT NULL,
  image VARCHAR(200) NOT NULL DEFAULT '',
  show_public TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_public (show_public, ach_date),
  KEY idx_member (member_id),
  CONSTRAINT fk_ach_member FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
