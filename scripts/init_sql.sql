-- 你 UI 的 SQL 用到 compset_rates；另外建兩張基礎表給預測模型學習
create table if not exists sales_daily(
  dt date primary key,
  revenue numeric,
  rooms_sold int
);

create table if not exists stays_daily(
  dt date primary key,
  occupancy numeric check(occupancy between 0 and 1)
);

create table if not exists compset_rates(
  dt date not null,
  brand text not null,
  price numeric not null,
  primary key (dt, brand)
);
