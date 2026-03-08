from .utils import *
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def html_download(html_path, title="", width=7, height=5, dpi=300, logo_size=(0.25, 0.25)):
    """
    Renders an HTML file to PNG and overlays a logo at the bottom right.

    Args:
        html_path (str): Local path to the HTML file.
        title (str): Title to display at the top of the HTML body.
        width (int): Viewport width in inches.
        height (int): Viewport height in inches.
        dpi (int): Rendering resolution in DPI.
        logo_size (tuple): Logo size in inches (width, height).

    Returns:
        io.BytesIO: Buffer containing the PNG image.
    """
    # Check height and width
    height = min(height, 5)
    width = min(width, 7)
    
    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument(f"--window-size={int(width*dpi)},{int(height*dpi)+150}")

    driver = webdriver.Chrome(options=chrome_options)

    # Load HTML page
    base_dir = '/'.join(tempfile.NamedTemporaryFile().name.split(os.sep)[:-1])
    abs_html_path = os.path.join(base_dir, html_path)
    driver.get(f"file://{abs_html_path}")
    
    # Add a dynamic header at the top of the body
    script = f"""
    const header = document.createElement("header");
    header.innerText = "{title}";
    header.style.textAlign = "center";
    header.style.fontSize = "{int(0.18*dpi)}px";
    header.style.fontWeight = "bold";
    header.style.color = "#444444";
    header.style.fontFamily = "Arial, sans-serif";

    document.body.insertBefore(header, document.body.firstChild);
    """
    driver.execute_script(script)
    time.sleep(0.5)  # Allow time for the header to render
    
    # Screenshot to temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        screenshot_path = tmp_file.name
    driver.save_screenshot(screenshot_path)
    driver.quit()

    # Load screenshot
    base = Image.open(screenshot_path).convert("RGBA")
    os.remove(screenshot_path)

    # Download and resize logo
    response = requests.get("https://raw.githubusercontent.com/massimoaria/bibliometrix/master/logo.png")
    logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
    # Calculate logo size in pixels based on dpi
    logo_pixel_size = (int(logo_size[0] * dpi), int(logo_size[1] * dpi))
    logo = logo.resize(logo_pixel_size, Image.LANCZOS)

    # Positioning
    positions = {
        "bottom-right": (base.width - logo_pixel_size[0] - 10, base.height - logo_pixel_size[1] - 10),
        "bottom-left": (10, base.height - logo_pixel_size[1] - 10),
        "top-right": (base.width - logo_pixel_size[0] - 10, 10),
        "top-left": (10, 10)
    }
    x, y = positions.get("bottom-right", positions["bottom-right"])

    # Composition
    composed = Image.new("RGBA", base.size)
    composed.paste(base, (0, 0))
    composed.paste(logo, (x, y), logo)

    # Write to buffer
    with io.BytesIO() as buffer:
        composed.convert("RGB").save(buffer, format="PNG", compress_level=0)
        return buffer.getvalue()
