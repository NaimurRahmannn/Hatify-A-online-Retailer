def build_product_context(products, max_products: int = 5) -> str:
    """
    Convert retrieved products into LLM-friendly context.
    Limits to top N products to save tokens and keep context concise.
    """
    if not products:
        return "No products found."

    context_parts = []
    for i, p in enumerate(products[:max_products], 1):
        name = p.get("name", "Unknown Product")
        price = p.get("price", "N/A")
        metadata = p.get("metadata", {})
        
        category = metadata.get("category", "N/A")
        colors = metadata.get("colors", [])
        sizes = metadata.get("sizes", [])
        brand = metadata.get("brand")
        material = metadata.get("material")
        style = metadata.get("style")
        occasion = metadata.get("occasion")
        season = metadata.get("season")
        gender = metadata.get("gender")
        fit = metadata.get("fit")
        rating = metadata.get("rating")
        in_stock = metadata.get("in_stock")
        description = metadata.get("description")
        
        color_str = ", ".join(colors) if colors else "N/A"
        size_str = ", ".join(sizes) if sizes else "N/A"

        product_str = f"Product {i}:\n"
        product_str += f"Name: {name}\n"
        product_str += f"Category: {category}\n"
        product_str += f"Price: {price} BDT\n"
        
        # Only add available fields
        if brand: product_str += f"Brand: {brand}\n"
        if colors: product_str += f"Color: {color_str}\n"
        if sizes: product_str += f"Sizes: {size_str}\n"
        if material: product_str += f"Material: {material}\n"
        if style: product_str += f"Style: {style}\n"
        if occasion: product_str += f"Occasion: {occasion}\n"
        if season: product_str += f"Season: {season}\n"
        if gender: product_str += f"Gender: {gender}\n"
        if fit: product_str += f"Fit: {fit}\n"
        if rating is not None: product_str += f"Rating: {rating}/5\n"
        if in_stock is not None: product_str += f"In Stock: {'Yes' if in_stock else 'No'}\n"
        if description: product_str += f"Description: {description}\n"
        
        context_parts.append(product_str)

    return "\n".join(context_parts)
