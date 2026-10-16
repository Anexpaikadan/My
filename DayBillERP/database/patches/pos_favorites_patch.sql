-- ============================================================
-- POS favourites: products marked with ⭐ in the Product form (or
-- the Product list right-click menu) appear as one-touch buttons on
-- the POS ★ Favourites tab. fav_order lets you sort them.
-- Safe to run more than once.
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('products') AND name = 'is_favorite')
    ALTER TABLE products ADD is_favorite BIT NOT NULL DEFAULT 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('products') AND name = 'fav_order')
    ALTER TABLE products ADD fav_order INT NOT NULL DEFAULT 0;
GO
PRINT 'POS favourites patch applied.';
GO
