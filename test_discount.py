import sys
from decimal import Decimal
import sys
import os

sys.path.append(os.getcwd())
from modules.pos import calculate_smart_total

cart = [
    {'item_name': 'Latte', 'price': '5.00', 'qty': 1, 'is_coffee': True},
    {'item_name': 'Keks', 'price': '3.00', 'qty': 1, 'is_coffee': False}
]

# Manual 10% discount
total, final, disc_rate, _, _, _, _ = calculate_smart_total(cart, manual_discount_percent=10)
print(f"Manual 10%: Total={total}, Final={final}, DiscRate={disc_rate}")
# Should be: Latte 5.00 - 10% = 4.50, Keks 3.00 - 0% = 3.00. Final = 7.50

# Customer Platinum (10%)
total, final, disc_rate, _, _, _, _ = calculate_smart_total(cart, customer={'type': 'platinum', 'stars': 0})
print(f"Platinum: Total={total}, Final={final}, DiscRate={disc_rate}")
# Should be: Latte 4.50 + Keks 3.00 = 7.50

# Ikram (100%)
total, final, disc_rate, _, _, _, _ = calculate_smart_total(cart, customer={'type': 'ikram', 'stars': 0})
print(f"Ikram: Total={total}, Final={final}, DiscRate={disc_rate}")
# Should be: Latte 0.00 + Keks 3.00 = 3.00

