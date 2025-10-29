 
# test_database.py
print("🔥 Probando database.py...")
try:
    from database import create_tables, engine
    print("✅ Database importado")
    
    create_tables()
    print("✅ Tablas creadas")
    
except Exception as e:
    print(f"❌ Error en database: {e}")
    import traceback
    traceback.print_exc()