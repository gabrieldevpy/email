from pypdf import PdfReader, PdfWriter
from docx import Document

def clean_pdf_metadata(input_path: str, output_path: str) -> None:
    """
    Reads a PDF, removes its core metadata properties, and saves it to a new file.
    This process inherently strips most metadata by creating a new document.

    Args:
        input_path: The path to the original PDF file.
        output_path: The path to save the cleaned PDF file.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    # Copy all pages from the reader to the writer
    for page in reader.pages:
        writer.add_page(page)

    # By not copying metadata, we effectively remove it.
    # We can also explicitly clear any remaining info if needed, though this is robust.

    # Write the cleaned content to the output file
    with open(output_path, 'wb') as f:
        writer.write(f)

def clean_docx_metadata(input_path: str, output_path: str) -> None:
    """
    Opens a DOCX document, clears its core metadata properties, and saves it to a new file.

    Args:
        input_path: The path to the original DOCX file.
        output_path: The path to save the cleaned DOCX file.
    """
    doc = Document(input_path)
    
    # Access and clear core properties
    properties = doc.core_properties
    properties.author = ""
    properties.title = ""
    properties.subject = ""
    properties.keywords = ""
    properties.comments = ""
    properties.last_modified_by = ""
    # Setting revision to 1 can also help clear modification history
    properties.revision = 1 
    # The created and modified dates can be set to a neutral value if desired,
    # but simply clearing text-based fields is most common.
    
    doc.save(output_path)

def clean_metadata(input_path: str) -> str:
    """
    Detects the file type and applies the appropriate metadata cleaning function,
    returning the path to the cleaned file.

    Args:
        input_path: The path to the original file (PDF or DOCX).

    Returns:
        The path to the newly created cleaned file.
    """
    if not input_path or not isinstance(input_path, str):
        raise ValueError("Invalid input path")

    file_ext = input_path.lower().split('.')[-1]
    # Create a new filename for the cleaned file
    cleaned_path = input_path.rsplit('.', 1)[0] + "_cleaned." + file_ext

    if file_ext == 'pdf':
        clean_pdf_metadata(input_path, cleaned_path)
    elif file_ext in ['doc', 'docx']:
        clean_docx_metadata(input_path, cleaned_path)
    else:
        # If the file type is not supported, return the original path
        return input_path
        
    return cleaned_path
