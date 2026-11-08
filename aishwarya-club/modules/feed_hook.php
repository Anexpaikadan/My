<?php
// ============================================================
// modules/feed_hook.php — Side-effect-free helper so other
// modules can publish into the community feed.
// Requires config.php to already be loaded (db(), SITE_URL).
// ============================================================
if (!function_exists('feed_add_market_post')) {
    function feed_add_market_post($itemId){
        try {
            db()->exec("CREATE TABLE IF NOT EXISTS feed_posts (
                id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, body TEXT DEFAULT NULL,
                media_type ENUM('none','image','video','link','market') DEFAULT 'none',
                media_url VARCHAR(700) DEFAULT NULL, link_url VARCHAR(700) DEFAULT NULL,
                link_title VARCHAR(300) DEFAULT NULL, link_thumb VARCHAR(700) DEFAULT NULL,
                ref_type VARCHAR(30) DEFAULT NULL, ref_id INT DEFAULT NULL,
                status ENUM('active','hidden') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id), INDEX idx_status (status), INDEX idx_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_type VARCHAR(30) DEFAULT NULL"); } catch(Exception $e){}
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_id INT DEFAULT NULL"); } catch(Exception $e){}
            try { db()->exec("ALTER TABLE feed_posts MODIFY media_type ENUM('none','image','video','link','market') DEFAULT 'none'"); } catch(Exception $e){}

            $dup = db()->prepare("SELECT id FROM feed_posts WHERE ref_type='market' AND ref_id=?");
            $dup->execute([$itemId]);
            if ($dup->fetch()) return false; // already posted

            $it = db()->prepare("SELECT m.*, (SELECT image_path FROM market_images WHERE item_id=m.id ORDER BY sort_order LIMIT 1) AS thumb
                                 FROM market_items m WHERE m.id=? AND m.status='active'");
            $it->execute([$itemId]);
            $row = $it->fetch();
            if (!$row) return false;

            $thumb = $row['thumb'] ? rtrim(SITE_URL,'/').'/assets/uploads/market/'.$row['thumb'] : '';
            $price = trim((string)$row['price']);
            $desc  = !empty($row['description']) ? "\n".mb_substr($row['description'],0,140) : '';
            $body  = '🏪 New in AV Market: '.$row['title'].($price !== '' ? ' — ₹'.$price : '').$desc;
            $linkUrl = rtrim(SITE_URL,'/').'/modules/market.php?view=item&id='.$itemId;

            db()->prepare("INSERT INTO feed_posts(user_id,body,media_type,media_url,link_url,link_title,link_thumb,ref_type,ref_id)
                           VALUES(?,?,?,?,?,?,?,?,?)")
               ->execute([(int)$row['user_id'], $body, 'market', '', $linkUrl, $row['title'], $thumb, 'market', $itemId]);
            return true;
        } catch (Exception $e) { return false; }
    }
}

if (!function_exists('feed_add_achievement_post')) {
    function feed_add_achievement_post($achId){
        try {
            // ensure feed table + columns exist (reuse market helper's table creation)
            db()->exec("CREATE TABLE IF NOT EXISTS feed_posts (
                id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, body TEXT DEFAULT NULL,
                media_type ENUM('none','image','video','link','market','videofile') DEFAULT 'none',
                media_url VARCHAR(700) DEFAULT NULL, link_url VARCHAR(700) DEFAULT NULL,
                link_title VARCHAR(300) DEFAULT NULL, link_thumb VARCHAR(700) DEFAULT NULL,
                thumb_url VARCHAR(700) DEFAULT NULL, ref_type VARCHAR(30) DEFAULT NULL, ref_id INT DEFAULT NULL,
                pinned TINYINT(1) DEFAULT 0, status ENUM('active','hidden') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_type VARCHAR(30) DEFAULT NULL"); } catch(Exception $e){}
            try { db()->exec("ALTER TABLE feed_posts ADD COLUMN ref_id INT DEFAULT NULL"); } catch(Exception $e){}

            // avoid duplicates
            $dup = db()->prepare("SELECT id FROM feed_posts WHERE ref_type='achievement' AND ref_id=?");
            $dup->execute([$achId]);
            if ($dup->fetch()) return false;

            $a = db()->prepare("SELECT * FROM achievements WHERE id=? AND status='active'");
            $a->execute([$achId]);
            $row = $a->fetch();
            if (!$row) return false;

            // resolve image path stored in feed_posts as relative (under assets/uploads/)
            $mediaRel = '';
            if (!empty($row['image'])) {
                $mediaRel = (strpos($row['image'],'/') !== false) ? $row['image'] : 'achievements/'.$row['image'];
            }
            $body = '🏆 Achievement: '.$row['member_name'].' — '.$row['title']
                  . (!empty($row['description']) ? "\n".$row['description'] : '');
            $uidPost = (int)($row['member_id'] ?: $row['created_by']);
            $mediaType = $mediaRel ? 'image' : 'none';

            db()->prepare("INSERT INTO feed_posts(user_id,body,media_type,media_url,ref_type,ref_id)
                           VALUES(?,?,?,?,?,?)")
               ->execute([$uidPost, $body, $mediaType, $mediaRel, 'achievement', $achId]);
            return true;
        } catch (Exception $e) { return false; }
    }
}

