from cs50 import SQL

db = SQL("sqlite:///finance.db")

# user = db.execute("SELECT * FROM users")
datas = db.execute("SELECT hash FROM users \
                    WHERE id = :U_id", U_id = 1)
# datas = []
# total = 0;
# s= 1;

print(datas[0]['hash'])