
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json, os
from config import BOT_TOKEN, ADMIN_CHAT_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

PRODUCTS_PATH = 'data/products.json'
MEDIA_DIR = 'media/'

# Загрузка каталога
def load_products():
    with open(PRODUCTS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# Сохранение каталога
def save_products(products):
    with open(PRODUCTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=4)

PRODUCTS = load_products()

user_states = {}
user_orders = {}
admin_states = {}

def get_product_keyboard(index):
    keyboard = InlineKeyboardMarkup()
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"nav_{index - 1}"))
    if index < len(PRODUCTS) - 1:
        buttons.append(InlineKeyboardButton("➡️ Вперёд", callback_data=f"nav_{index + 1}"))
    keyboard.row(*buttons)
    keyboard.add(InlineKeyboardButton("🛍 Заказать", callback_data=f"order_{PRODUCTS[index]['id']}"))
    return keyboard

@dp.message_handler(commands=['start', 'menu'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📦 Каталог букетов", callback_data="menu_catalog"),
        InlineKeyboardButton("ℹ️ О нас", callback_data="menu_about"),
        InlineKeyboardButton("☎️ Контакты", callback_data="menu_contacts")
    )
    await message.answer("Добро пожаловать в *ленточный бот*!\nВыберите действие:", reply_markup=kb, parse_mode="Markdown")
    user_states[message.from_user.id] = {"index": 0}
    await show_product(message.from_user.id, 0)

async def show_product(user_id, index):
    product = PRODUCTS[index]
    photo = types.InputFile(product["photo"])
    caption = f"<b>🎀 {product['name']}</b>\n\n📝 {product['description']}"
    keyboard = get_product_keyboard(index)
    await bot.send_photo(user_id, photo, caption=caption, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith("nav_"))
async def navigate_catalog(callback: types.CallbackQuery):
    index = int(callback.data.split("_")[1])
    user_states[callback.from_user.id]["index"] = index
    await show_product(callback.from_user.id, index)

@dp.callback_query_handler(lambda c: c.data.startswith("order_"))
async def start_order(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_orders[callback.from_user.id] = {"product_id": product_id}
    await bot.send_message(callback.from_user.id, "Сколько штук вы хотите заказать?")

@dp.message_handler(lambda m: m.from_user.id in user_orders and 'quantity' not in user_orders[m.from_user.id])
async def get_quantity(message: types.Message):
    try:
        qty = int(message.text.strip())
        if qty < 1:
            raise ValueError
        user_orders[message.from_user.id]['quantity'] = qty
        await message.answer("Введите ваше имя:")
    except:
        await message.answer("Пожалуйста, введите корректное количество (целое число больше 0).")

@dp.message_handler(lambda m: m.from_user.id in user_orders and 'name' not in user_orders[m.from_user.id])
async def get_name(message: types.Message):
    user_orders[message.from_user.id]['name'] = message.text.strip()
    await message.answer("Введите номер телефона:")

@dp.message_handler(lambda m: m.from_user.id in user_orders and 'phone' not in user_orders[m.from_user.id])
async def get_phone(message: types.Message):
    phone = message.text.strip()
    if not phone.startswith('+') or not any(c.isdigit() for c in phone):
        await message.answer("Пожалуйста, введите номер телефона в формате +7...")
        return
    user_orders[message.from_user.id]['phone'] = phone
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Пропустить", callback_data="skip_comment")
    )
    await message.answer("Хотите добавить комментарий к заказу?", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "skip_comment")
async def skip_comment(callback: types.CallbackQuery):
    user_orders[callback.from_user.id]['comment'] = "-"
    await finish_order(callback.from_user.id)

@dp.message_handler(lambda m: m.from_user.id in user_orders and 'comment' not in user_orders[m.from_user.id])
async def get_comment(message: types.Message):
    user_orders[message.from_user.id]['comment'] = message.text.strip()
    await finish_order(message.from_user.id)

async def finish_order(user_id):
    order = user_orders.pop(user_id)
    product = next((p for p in PRODUCTS if p["id"] == order["product_id"]), None)
    if product:
        msg = (
            f"<b>🌹 Новый заказ!</b>\n"
            f"Товар: {product['name']}\n"
            f"Количество: {order['quantity']}\n"
            f"Имя: {order['name']}\n"
            f"Телефон: {order['phone']}\n"
            f"Комментарий: {order['comment']}"
        )
        keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Принять", callback_data=f"confirm_{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
    )
    await bot.send_message(ADMIN_CHAT_ID, msg, reply_markup=keyboard, parse_mode="HTML")
        await bot.send_message(user_id, "Спасибо за заказ! Мы свяжемся с вами в ближайшее время.")
    else:
        await bot.send_message(user_id, "Произошла ошибка при оформлении заказа.")

# --- Админ-панель ---

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("✏️ Редактировать букет", callback_data="admin_edit"),
        InlineKeyboardButton("❌ Удалить букет", callback_data="admin_delete"),
        InlineKeyboardButton("➕ Добавить букет", callback_data="admin_add"),
        InlineKeyboardButton("📋 Список букетов", callback_data="admin_list")
    )
    await message.answer("Админ-панель:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_add")
async def admin_add(callback: types.CallbackQuery):
    admin_states[callback.from_user.id] = {"step": "photo"}
    await bot.send_message(callback.from_user.id, "Отправьте фото нового букета.")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def admin_photo(message: types.Message):
    state = admin_states.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_path = os.path.join(MEDIA_DIR, f"bouquet_{file.file_unique_id}.jpg")
    await photo.download(destination_file=photo_path)
    state["photo"] = photo_path
    state["step"] = "name"
    await message.answer("Введите название букета:")

@dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id].get("step") == "name")
async def admin_name(message: types.Message):
    admin_states[message.from_user.id]["name"] = message.text.strip()
    admin_states[message.from_user.id]["step"] = "desc"
    await message.answer("Введите описание букета:")

@dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id].get("step") == "desc")
async def admin_desc(message: types.Message):
    state = admin_states.pop(message.from_user.id)
    new_product = {
        "id": max(p["id"] for p in PRODUCTS) + 1 if PRODUCTS else 1,
        "name": state["name"],
        "description": message.text.strip(),
        "photo": state["photo"]
    }
    PRODUCTS.append(new_product)
    save_products(PRODUCTS)
    await message.answer("Букет успешно добавлен в каталог!")

@dp.callback_query_handler(lambda c: c.data == "admin_list")
async def admin_list(callback: types.CallbackQuery):
    text = "\n".join([f"{p['id']}: {p['name']}" for p in PRODUCTS])
    await bot.send_message(callback.from_user.id, f"Текущий каталог:\n{text}")
    
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

# Подтверждение/отказ
@dp.callback_query_handler(lambda c: c.data.startswith("confirm_") or c.data.startswith("reject_"))
async def handle_order_response(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    if callback.data.startswith("confirm_"):
        await bot.send_message(user_id, "Ваш заказ подтверждён. Спасибо за покупку!")
        await callback.message.edit_reply_markup()
    elif callback.data.startswith("reject_"):
        await bot.send_message(user_id, "К сожалению, ваш заказ был отклонён. Свяжитесь с нами для уточнения.")
        await callback.message.edit_reply_markup()

@dp.callback_query_handler(lambda c: c.data == "admin_delete")
async def admin_delete(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    for p in PRODUCTS:
        kb.add(InlineKeyboardButton(f"{p['name']}", callback_data=f"del_{p['id']}"))
    await bot.send_message(callback.from_user.id, "Выберите букет для удаления:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("del_"))
async def confirm_delete(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        await callback.message.answer("Товар не найден.")
        return
    PRODUCTS.remove(product)
    save_products(PRODUCTS)
    await callback.message.answer(f"Букет '{product['name']}' удалён.")

@dp.callback_query_handler(lambda c: c.data == "admin_edit")
async def admin_edit(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    for p in PRODUCTS:
        kb.add(InlineKeyboardButton(f"{p['name']}", callback_data=f"edit_{p['id']}"))
    await bot.send_message(callback.from_user.id, "Выберите букет для редактирования:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("edit_"))
async def select_edit(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    admin_states[callback.from_user.id] = {"step": "edit_field", "edit_id": pid}
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Название", callback_data="edit_field_name"),
        InlineKeyboardButton("Описание", callback_data="edit_field_desc")
    )
    await bot.send_message(callback.from_user.id, "Что вы хотите изменить?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("edit_field_"))
async def choose_edit_field(callback: types.CallbackQuery):
    field = callback.data.split("_")[2]
    state = admin_states.get(callback.from_user.id, {})
    state["field"] = field
    state["step"] = "edit_input"
    await bot.send_message(callback.from_user.id, f"Введите новое значение для {field}:")

@dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id].get("step") == "edit_input")
async def update_edit_field(message: types.Message):
    state = admin_states.pop(message.from_user.id)
    pid = state["edit_id"]
    field = state["field"]
    product = next((p for p in PRODUCTS if p["id"] == pid), None)
    if product:
        product[field] = message.text.strip()
        save_products(PRODUCTS)
        await message.answer("Изменения сохранены.")
    else:
        await message.answer("Ошибка: товар не найден.")

# Главное меню кнопок
@dp.callback_query_handler(lambda c: c.data == "menu_catalog")
async def menu_catalog(callback: types.CallbackQuery):
    user_states[callback.from_user.id] = {"index": 0}
    await show_product(callback.from_user.id, 0)

@dp.callback_query_handler(lambda c: c.data == "menu_about")
async def menu_about(callback: types.CallbackQuery):
    text = "🌸 *О нас*:\nМы создаём уникальные букеты из атласных лент вручную с любовью.\nИдеально для подарка, декора или событий."
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "menu_contacts")
async def menu_contacts(callback: types.CallbackQuery):
    text = "📞 *Контакты*:\nТелефон: +7 (999) 123-45-67\nInstagram: @ribbon.flowers\nГород: Москва"
    await callback.message.answer(text, parse_mode="Markdown")
