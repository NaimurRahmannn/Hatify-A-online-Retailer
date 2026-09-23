from ai_search.models import ProductSearchDocument

def generate_product_document(product):
    """
    Generates AI-friendly document for a Product and saves it to ProductSearchDocument.
    """
    name = product.product_name
    description = product.product_description
    category_name = product.category.categroy_name if product.category else ""
    category_type = product.category.get_category_type_display() if product.category else ""
    price = str(product.price)
    
    colors = [cv.color_name for cv in product.color_variant.all()]
    sizes = [sv.size_name for sv in product.size_variant.all()]
    
    lines = [
        f"{name}.",
        f"Category: {category_name} ({category_type}).",
    ]
    if colors:
        lines.append(f"Color: {', '.join(colors)}.")
    if sizes:
        lines.append(f"Available sizes: {', '.join(sizes)}.")
    lines.append(f"Price: {price}.")
    lines.append(f"Description: {description}")
    
    searchable_text = "\n".join(lines)
    
    metadata = {
        "category": category_name,
        "category_type": category_type,
        "price": float(product.price),
        "colors": colors,
        "sizes": sizes,
    }
    
    doc, created = ProductSearchDocument.objects.update_or_create(
        product=product,
        defaults={
            "searchable_text": searchable_text,
            "metadata": metadata
        }
    )
    return doc
