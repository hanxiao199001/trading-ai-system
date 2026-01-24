import sqlite3
import os
from datetime import datetime

def upgrade_database():
    """升级trading.db数据库结构"""
    
    # 在项目根目录查找trading.db
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 可能的数据库位置
    possible_paths = [
        os.path.join(project_root, 'database', 'trading.db'),
        os.path.join(project_root, 'data', 'trading.db'),
        os.path.join(project_root, 'data', 'storage', 'trading.db'),
        os.path.join(project_root, 'trading.db')
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            print(f"✅ 找到数据库: {db_path}")
            break
    
    if not db_path:
        print("❌ 未找到trading.db,可能的位置:")
        for path in possible_paths:
            print(f"  - {path}")
        
        # 创建新数据库
        db_path = os.path.join(project_root, 'database', 'trading.db')
        print(f"\n📦 创建新数据库: {db_path}")
    
    # 备份
    if os.path.exists(db_path):
        backup_path = db_path.replace('.db', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        print(f"📦 备份数据库到: {backup_path}")
        os.system(f'cp "{db_path}" "{backup_path}"')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n🔧 开始升级数据库...")
        
        # 创建表1: 现货价格
        print("  📊 创建表: spot_prices")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spot_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                volume_24h REAL,
                bid REAL,
                ask REAL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建表2: 期货价格
        print("  📊 创建表: futures_prices")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS futures_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                mark_price REAL,
                index_price REAL,
                open_interest REAL,
                volume_24h REAL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建表3: 套利机会
        print("  📊 创建表: arbitrage_opportunities")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                spot_price REAL NOT NULL,
                futures_price REAL NOT NULL,
                basis REAL NOT NULL,
                basis_rate REAL NOT NULL,
                annualized_basis REAL,
                funding_rate REAL,
                funding_cost_7d REAL,
                borrow_rate REAL,
                total_cost REAL,
                net_return REAL,
                is_profitable BOOLEAN,
                arbitrage_type TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建表4: 套利持仓
        print("  📊 创建表: arbitrage_positions")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS arbitrage_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT UNIQUE NOT NULL,
                open_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                close_time DATETIME,
                symbol TEXT NOT NULL,
                spot_entry_price REAL NOT NULL,
                futures_entry_price REAL NOT NULL,
                position_size REAL NOT NULL,
                spot_order_id TEXT,
                futures_order_id TEXT,
                spot_exit_price REAL,
                futures_exit_price REAL,
                spot_close_order_id TEXT,
                futures_close_order_id TEXT,
                expected_return REAL,
                actual_return REAL,
                pnl_usdt REAL,
                status TEXT NOT NULL,
                close_reason TEXT,
                notes TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建表5: 借币利率
        print("  📊 创建表: borrow_rates")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS borrow_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                daily_rate REAL NOT NULL,
                annualized_rate REAL NOT NULL,
                source TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        print("\n🔍 创建索引...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_spot_symbol_time ON spot_prices(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_futures_symbol_time ON futures_prices(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_arb_symbol_time ON arbitrage_opportunities(symbol, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_arb_profitable ON arbitrage_opportunities(is_profitable, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_pos_status ON arbitrage_positions(status)"
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
        
        conn.commit()
        
        # 验证
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("\n✅ 数据库表清单:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  ✓ {table[0]} ({count} 条记录)")
        
        conn.close()
        
        print("\n" + "="*50)
        print("🎉 数据库升级完成!")
        print("="*50)
        print(f"📍 数据库位置: {db_path}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 升级失败: {e}")
        return False


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════╗
    ║  Trading AI System - Database Upgrade      ║
    ╚════════════════════════════════════════════╝
    """)
    
    upgrade_database()
