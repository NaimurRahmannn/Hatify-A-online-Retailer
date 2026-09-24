def build_product_context(products) -> str:
    """
    Convert retrieved products into LLM-friendly context.
    """
    if not products:
        return "No products found."

    context_parts = []
    for i, p in enumerate(products, 1):
        # Extract attributes from metadata if available
        # The products passed here might be ProductSearchDocument or Product
        # Let's assume they are the dictionaries returned by retrieve_products 
        # which looks like: {"id": "...", "name": "...", "price": "...", "metadata": {...}}
        
        name = p.get("name", "Unknown Product")
        price = p.get("price", "N/A")
        metadata = p.get("metadata", {})
        
        category = metadata.get("category", "N/A")
        colors = metadata.get("colors", [])
        sizes = metadata.get("sizes", [])
        description = metadata.get("description", "N/A")
        
        color_str = ", ".join(colors) if colors else "N/A"
        size_str = ", ".join(sizes) if sizes else "N/A"

        product_str = f"Product {i}:\n"
        product_str += f"Name: {name}\n"
        product_str += f"Category: {category}\n"
        product_str += f"Price: {price} BDT\n"
        product_str += f"Color: {color_str}\n"
        product_str += f"Sizes: {size_str}\n"
        product_str += f"Description: {description}\n"
        
        context_parts.append(product_str)

    return "\n".join(context_parts)
