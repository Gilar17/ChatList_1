from PIL import Image, ImageDraw

BG_BLUE = (25, 118, 210)
DOT_BLUE = (25, 118, 210)
WHITE = (255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    """Рисует иконку ChatList: синий фон, белое облако сообщения, три синие точки."""
    img = Image.new("RGBA", (size, size), BG_BLUE + (255,))
    draw = ImageDraw.Draw(img)

    margin = max(2, round(size * 0.10))
    bubble_width = size - margin * 2
    bubble_height = max(margin * 2, round(bubble_width * 0.70))
    bubble_left = margin
    bubble_top = (size - bubble_height) // 2
    bubble_right = bubble_left + bubble_width
    bubble_bottom = bubble_top + bubble_height
    corner_radius = max(2, round(min(bubble_width, bubble_height) * 0.24))

    draw.rounded_rectangle(
        (bubble_left, bubble_top, bubble_right, bubble_bottom),
        radius=corner_radius,
        fill=WHITE,
    )

    dot_radius = max(1, round(size * 0.058))
    dot_spacing = max(dot_radius * 2 + 1, round(size * 0.115))
    dots_y = bubble_top + bubble_height // 2
    dots_x_start = size // 2 - dot_spacing

    for index in range(3):
        center_x = dots_x_start + index * dot_spacing
        draw.ellipse(
            (
                center_x - dot_radius,
                dots_y - dot_radius,
                center_x + dot_radius,
                dots_y + dot_radius,
            ),
            fill=DOT_BLUE,
        )

    return img.convert("RGB")


SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
icons = [draw_icon(width) for width, _ in SIZES]

try:
    icons[0].save(
        "app.ico",
        format="ICO",
        sizes=SIZES,
        append_images=icons[1:],
    )
    print("Иконка 'app.ico' создана.")
    print("Дизайн: синий фон, белое облако сообщения, три синие точки.")
except Exception as error:
    print(f"Ошибка при сохранении: {error}")
    icons[0].save("app.ico", format="ICO")
    print("Иконка 'app.ico' создана (только один размер).")
