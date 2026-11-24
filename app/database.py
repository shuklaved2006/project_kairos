from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, JSON, Index
from sqlalchemy.pool import StaticPool

metadata = MetaData()
records = Table('records', metadata,
    Column('id', String(128), primary_key=True),
    Column('owner_id', String(36), nullable=True),
    Column('kind', String(40), nullable=False),
    Column('version', Integer, nullable=False, default=1),
    Column('data', JSON, nullable=False))
Index('ix_records_owner_kind', records.c.owner_id, records.c.kind)

def database(url):
    if url.startswith('sqlite'):
        options = {'connect_args': {'check_same_thread': False}}
        if url == 'sqlite://':
            options['poolclass'] = StaticPool
        engine = create_engine(url, **options)
        metadata.create_all(engine)
        return engine
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if not url.startswith('postgresql+psycopg://'):
        raise ValueError('Use PostgreSQL/psycopg or SQLite for tests')
    # Supabase transaction pooler: no prepared statements, minimal pool, TLS.
    # Schema migrations are intentionally separate from function initialization.
    return create_engine(url, pool_size=1, max_overflow=0, pool_timeout=15,
                         pool_pre_ping=True, hide_parameters=True,
                         connect_args={'prepare_threshold':None, 'sslmode':'require', 'connect_timeout':10})
