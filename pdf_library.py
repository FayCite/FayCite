import PyPDF2
from typing import Dict, List, Optional
import io
import re

class PDFLibrary:
    def __init__(self):
        """Initialize the PDF library storage."""
        self.library = {}  # filename -> content dictionary
    
    def add_pdf(self, pdf_file) -> bool:
        """
        Add a PDF file to the library and extract its content.
        
        Args:
            pdf_file: Streamlit uploaded file object
            
        Returns:
            True if successfully added, False otherwise
        """
        try:
            # Reset file pointer
            pdf_file.seek(0)
            
            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
            
            # Extract text from all pages
            content_by_page = []
            full_text = ""
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        content_by_page.append({
                            'page': page_num,
                            'text': page_text.strip()
                        })
                        full_text += page_text + "\n"
                except Exception as e:
                    print(f"Error extracting text from page {page_num}: {str(e)}")
                    continue
            
            if content_by_page:
                self.library[pdf_file.name] = {
                    'filename': pdf_file.name,
                    'full_text': full_text,
                    'pages': content_by_page,
                    'metadata': self._extract_metadata(pdf_reader)
                }
                return True
            else:
                print(f"No readable text found in {pdf_file.name}")
                return False
                
        except Exception as e:
            print(f"Error processing PDF {pdf_file.name}: {str(e)}")
            return False
    
    def remove_pdf(self, filename: str) -> bool:
        """
        Remove a PDF from the library.
        
        Args:
            filename: Name of the file to remove
            
        Returns:
            True if removed, False if not found
        """
        if filename in self.library:
            del self.library[filename]
            return True
        return False
    
    def get_library_files(self) -> List[str]:
        """
        Get list of all files in the library.
        
        Returns:
            List of filenames
        """
        return list(self.library.keys())
    
    def get_pdf_content(self, filename: str) -> Optional[Dict]:
        """
        Get content of a specific PDF.
        
        Args:
            filename: Name of the PDF file
            
        Returns:
            Content dictionary or None if not found
        """
        return self.library.get(filename)
    
    def get_all_content(self) -> List[Dict]:
        """
        Get all content from the library for searching.
        
        Returns:
            List of content dictionaries with page-level granularity
        """
        all_content = []
        
        for filename, pdf_data in self.library.items():
            for page_data in pdf_data['pages']:
                # Split page content into chunks for better matching
                chunks = self._split_into_chunks(page_data['text'])
                
                for chunk in chunks:
                    if len(chunk.strip()) > 50:  # Only include substantial chunks
                        all_content.append({
                            'filename': filename,
                            'page': page_data['page'],
                            'text': chunk,
                            'metadata': pdf_data['metadata']
                        })
        
        return all_content
    
    def search_content(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search for content matching a query.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of matching content
        """
        results = []
        query_lower = query.lower()
        
        for filename, pdf_data in self.library.items():
            for page_data in pdf_data['pages']:
                if query_lower in page_data['text'].lower():
                    # Find the context around the match
                    context = self._extract_context(page_data['text'], query, 200)
                    
                    results.append({
                        'filename': filename,
                        'page': page_data['page'],
                        'text': context,
                        'metadata': pdf_data['metadata']
                    })
                    
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def _extract_metadata(self, pdf_reader) -> Dict:
        """
        Extract comprehensive metadata from PDF properties and text content.
        
        Args:
            pdf_reader: PyPDF2 PdfReader object
            
        Returns:
            Enhanced metadata dictionary
        """
        metadata = {
            'title': '',
            'authors': [],
            'author': '',  # Keep for backward compatibility
            'subject': '',
            'abstract': '',
            'keywords': [],
            'doi': '',
            'journal': '',
            'year': '',
            'volume': '',
            'issue': '',
            'pages': '',
            'publisher': '',
            'creator': '',
            'producer': '',
            'creation_date': '',
            'modification_date': '',
            'num_pages': 0,
            'is_academic_paper': False,
            'confidence_score': 0.0
        }
        
        try:
            # Extract basic PDF metadata
            if pdf_reader.metadata:
                raw_title = pdf_reader.metadata.get('/Title', '').strip()
                raw_author = pdf_reader.metadata.get('/Author', '').strip()
                raw_subject = pdf_reader.metadata.get('/Subject', '').strip()
                
                # Clean and process title
                metadata['title'] = self._clean_title(raw_title)
                
                # Parse and clean authors
                if raw_author:
                    metadata['authors'] = self._parse_authors(raw_author)
                    metadata['author'] = raw_author  # Keep original for compatibility
                
                # Extract subject/keywords
                metadata['subject'] = raw_subject
                if raw_subject:
                    metadata['keywords'] = self._extract_keywords(raw_subject)
                
                # Other metadata
                metadata['creator'] = pdf_reader.metadata.get('/Creator', '').strip()
                metadata['producer'] = pdf_reader.metadata.get('/Producer', '').strip()
                metadata['creation_date'] = str(pdf_reader.metadata.get('/CreationDate', ''))
                metadata['modification_date'] = str(pdf_reader.metadata.get('/ModDate', ''))
                
                # Extract year from creation date if available
                if not metadata['year']:
                    metadata['year'] = self._extract_year_from_date(metadata['creation_date'])
            
            metadata['num_pages'] = len(pdf_reader.pages)
            
            # Extract text-based metadata from first few pages
            text_metadata = self._extract_text_based_metadata(pdf_reader)
            
            # Merge text-based metadata with PDF metadata (text-based takes precedence if more complete)
            metadata = self._merge_metadata(metadata, text_metadata)
            
            # Determine if this looks like an academic paper
            metadata['is_academic_paper'], metadata['confidence_score'] = self._assess_academic_paper(metadata, pdf_reader)
            
        except Exception as e:
            print(f"Error extracting metadata: {str(e)}")
        
        return metadata
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize a title string."""
        if not title:
            return ''
        
        # Remove common prefixes and suffixes
        title = title.strip()
        title = re.sub(r'^(Microsoft Word - |Adobe PDF - )', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\.(pdf|doc|docx)$', '', title, flags=re.IGNORECASE)
        
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def _parse_authors(self, author_string: str) -> List[str]:
        """Parse author string into list of individual authors."""
        if not author_string:
            return []
        
        authors = []
        
        # Split by common delimiters
        for delimiter in [';', ',', ' and ', ' & ', '\n']:
            if delimiter in author_string:
                parts = author_string.split(delimiter)
                authors = [part.strip() for part in parts if part.strip()]
                break
        
        if not authors:
            authors = [author_string.strip()]
        
        # Clean up individual author names
        cleaned_authors = []
        for author in authors:
            # Remove email addresses and affiliations in parentheses
            author = re.sub(r'\([^)]*\)', '', author)
            author = re.sub(r'<[^>]*>', '', author)
            author = author.strip()
            if author and len(author) > 2:
                cleaned_authors.append(author)
        
        return cleaned_authors
    
    def _extract_keywords(self, subject: str) -> List[str]:
        """Extract keywords from subject field."""
        if not subject:
            return []
        
        # Split by common delimiters
        keywords = []
        for delimiter in [';', ',', '|', '\n']:
            if delimiter in subject:
                keywords = [kw.strip() for kw in subject.split(delimiter) if kw.strip()]
                break
        
        if not keywords:
            keywords = [subject.strip()]
        
        return [kw for kw in keywords if len(kw) > 2]
    
    def _extract_year_from_date(self, date_string: str) -> str:
        """Extract year from date string."""
        if not date_string:
            return ''
        
        # Try to find 4-digit year
        year_match = re.search(r'(\d{4})', date_string)
        if year_match:
            year = int(year_match.group(1))
            # Only return reasonable years for academic papers
            if 1900 <= year <= 2030:
                return str(year)
        
        return ''
    
    def _extract_text_based_metadata(self, pdf_reader) -> Dict:
        """Extract metadata from PDF text content (first few pages)."""
        metadata = {
            'title': '',
            'authors': [],
            'abstract': '',
            'doi': '',
            'journal': '',
            'year': '',
            'volume': '',
            'issue': '',
            'pages': '',
            'publisher': '',
            'keywords': []
        }
        
        try:
            # Extract text from first 3 pages for metadata
            first_pages_text = ""
            max_pages = min(3, len(pdf_reader.pages))
            
            for i in range(max_pages):
                try:
                    page_text = pdf_reader.pages[i].extract_text()
                    if page_text:
                        first_pages_text += page_text + "\n"
                except Exception:
                    continue
            
            if not first_pages_text:
                return metadata
            
            # Extract DOI
            metadata['doi'] = self._extract_doi_from_text(first_pages_text)
            
            # Extract title from text
            text_title = self._extract_title_from_text(first_pages_text)
            if text_title:
                metadata['title'] = text_title
            
            # Extract authors from text
            text_authors = self._extract_authors_from_text(first_pages_text)
            if text_authors:
                metadata['authors'] = text_authors
            
            # Extract journal information
            journal_info = self._extract_journal_info(first_pages_text)
            metadata.update(journal_info)
            
            # Extract year from text
            if not metadata['year']:
                metadata['year'] = self._extract_year_from_text(first_pages_text)
            
            # Extract abstract
            metadata['abstract'] = self._extract_abstract(first_pages_text)
            
        except Exception as e:
            print(f"Error in text-based metadata extraction: {str(e)}")
        
        return metadata
    
    def _extract_doi_from_text(self, text: str) -> str:
        """Extract DOI from text using comprehensive regex patterns."""
        if not text:
            return ''
        
        # Common DOI patterns
        doi_patterns = [
            r'doi:\s*([10]\.\d+\/[^\s]+)',
            r'DOI:\s*([10]\.\d+\/[^\s]+)',
            r'https?://doi\.org/([10]\.\d+\/[^\s]+)',
            r'https?://dx\.doi\.org/([10]\.\d+\/[^\s]+)',
            r'doi\.org/([10]\.\d+\/[^\s]+)',
            r'(10\.\d+\/[^\s,;]+)',  # Generic DOI pattern
        ]
        
        for pattern in doi_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doi = match.group(1)
                # Clean up DOI
                doi = re.sub(r'[.,;)]$', '', doi)  # Remove trailing punctuation
                if len(doi) > 7:  # Minimum reasonable DOI length
                    return doi
        
        return ''
    
    def _extract_title_from_text(self, text: str) -> str:
        """Extract title from PDF text content."""
        if not text:
            return ''
        
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        if not lines:
            return ''
        
        # Look for title in first few lines
        for i, line in enumerate(lines[:10]):
            # Skip very short lines or lines with lots of special characters
            if len(line) < 10 or len(re.findall(r'[^\w\s]', line)) / len(line) > 0.3:
                continue
            
            # Skip lines that look like headers, footers, or metadata
            if any(keyword in line.lower() for keyword in ['page', 'volume', 'journal', 'doi', 'abstract', 'keywords', 'introduction']):
                continue
            
            # Title is likely to be one of the longer lines at the beginning
            if len(line) > 20 and len(line) < 200:
                # Check if next lines might be continuation
                full_title = line
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j]
                    if len(next_line) > 10 and len(next_line) < 100 and not any(keyword in next_line.lower() for keyword in ['author', 'university', 'department', 'email']):
                        full_title += " " + next_line
                    else:
                        break
                
                return full_title.strip()
        
        return ''
    
    def _extract_authors_from_text(self, text: str) -> List[str]:
        """Extract authors from PDF text content."""
        if not text:
            return []
        
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        authors = []
        
        # Look for author patterns in first 20 lines
        for i, line in enumerate(lines[:20]):
            # Skip very short lines
            if len(line) < 3:
                continue
            
            # Look for lines that might contain author names
            # Authors often appear after title and before abstract/keywords
            if any(keyword in line.lower() for keyword in ['author', 'by ']):
                # Extract names after "author" or "by"
                author_text = re.sub(r'^.*?(author|by)\s*:?\s*', '', line, flags=re.IGNORECASE)
                if author_text:
                    authors.extend(self._parse_authors(author_text))
            
            # Look for lines with name patterns (First Last, First Last)
            name_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+(?:,\s*[A-Z][a-z]+ [A-Z][a-z]+)*)'
            matches = re.findall(name_pattern, line)
            for match in matches:
                if len(match) > 5 and len(match) < 100:  # Reasonable author name length
                    authors.extend(self._parse_authors(match))
        
        # Remove duplicates and clean
        unique_authors = []
        for author in authors:
            if author not in unique_authors and len(author) > 2:
                unique_authors.append(author)
        
        return unique_authors[:10]  # Limit to reasonable number
    
    def _extract_journal_info(self, text: str) -> Dict:
        """Extract journal, volume, issue, and page information."""
        info = {'journal': '', 'volume': '', 'issue': '', 'pages': '', 'publisher': ''}
        
        if not text:
            return info
        
        lines = text.split('\n')
        
        # Look for journal patterns in first 30 lines
        for line in lines[:30]:
            line = line.strip()
            if len(line) < 5:
                continue
            
            # Journal name patterns
            journal_indicators = ['journal', 'proceedings', 'conference', 'international', 'ieee', 'acm', 'springer', 'elsevier']
            if any(indicator in line.lower() for indicator in journal_indicators):
                # Extract journal name
                if not info['journal'] and len(line) < 150:
                    # Clean up potential journal name
                    journal = re.sub(r'(volume|vol|issue|no|pp?\.)\s*\d+.*$', '', line, flags=re.IGNORECASE)
                    journal = re.sub(r'\d{4}.*$', '', journal)  # Remove year and everything after
                    journal = journal.strip()
                    if len(journal) > 5:
                        info['journal'] = journal
            
            # Volume and issue patterns
            vol_pattern = r'vol(?:ume)?\s*\.?\s*(\d+)'
            vol_match = re.search(vol_pattern, line, re.IGNORECASE)
            if vol_match and not info['volume']:
                info['volume'] = vol_match.group(1)
            
            issue_pattern = r'(?:issue|no|number)\s*\.?\s*(\d+)'
            issue_match = re.search(issue_pattern, line, re.IGNORECASE)
            if issue_match and not info['issue']:
                info['issue'] = issue_match.group(1)
            
            # Page patterns
            page_pattern = r'pp?\.\s*(\d+(?:-\d+)?)'
            page_match = re.search(page_pattern, line, re.IGNORECASE)
            if page_match and not info['pages']:
                info['pages'] = page_match.group(1)
            
            # Publisher patterns
            publishers = ['springer', 'elsevier', 'ieee', 'acm', 'wiley', 'taylor', 'francis', 'sage', 'oxford', 'cambridge']
            for publisher in publishers:
                if publisher in line.lower() and not info['publisher']:
                    info['publisher'] = publisher.title()
                    break
        
        return info
    
    def _extract_year_from_text(self, text: str) -> str:
        """Extract publication year from text content."""
        if not text:
            return ''
        
        # Look for year patterns in first 50 lines
        lines = text.split('\n')[:50]
        
        for line in lines:
            # Look for 4-digit years, prioritizing those near publication keywords
            year_matches = re.findall(r'(\d{4})', line)
            for year_str in year_matches:
                year = int(year_str)
                if 1900 <= year <= 2030:
                    # Check if year appears near publication-related keywords
                    context = line.lower()
                    if any(keyword in context for keyword in ['published', 'copyright', '©', 'journal', 'conference', 'proceedings']):
                        return year_str
                    # Or if it's just a reasonable recent year
                    if 1980 <= year <= 2030:
                        return year_str
        
        return ''
    
    def _extract_abstract(self, text: str) -> str:
        """Extract abstract from PDF text."""
        if not text:
            return ''
        
        # Look for abstract section
        abstract_pattern = r'abstract\s*[:\-]?\s*(.*?)(?=\n\s*(?:keywords|introduction|1\.|\d+\.|references))'
        match = re.search(abstract_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            abstract = match.group(1).strip()
            # Clean up the abstract
            abstract = re.sub(r'\s+', ' ', abstract)
            if 50 < len(abstract) < 2000:  # Reasonable abstract length
                return abstract
        
        return ''
    
    def _merge_metadata(self, pdf_metadata: Dict, text_metadata: Dict) -> Dict:
        """Merge PDF metadata with text-based metadata."""
        merged = pdf_metadata.copy()
        
        # Text-based extraction takes precedence for key fields if more complete
        for key in ['title', 'authors', 'doi', 'journal', 'year', 'abstract']:
            text_value = text_metadata.get(key, '')
            if text_value and (not merged.get(key) or len(str(text_value)) > len(str(merged.get(key, '')))):
                merged[key] = text_value
        
        # Merge other fields additively
        for key in ['volume', 'issue', 'pages', 'publisher', 'keywords']:
            if text_metadata.get(key) and not merged.get(key):
                merged[key] = text_metadata[key]
        
        # Update author field for compatibility
        if merged.get('authors') and not merged.get('author'):
            merged['author'] = ', '.join(merged['authors'])
        
        return merged
    
    def _assess_academic_paper(self, metadata: Dict, pdf_reader) -> tuple:
        """Assess whether this PDF is likely an academic paper and return confidence score."""
        score = 0.0
        max_score = 10.0
        
        # Check for academic indicators in metadata
        if metadata.get('doi'):
            score += 2.0
        
        if metadata.get('journal'):
            score += 1.5
        
        if metadata.get('abstract'):
            score += 1.0
        
        if metadata.get('authors') and len(metadata['authors']) > 1:
            score += 1.0
        
        if metadata.get('year'):
            year = int(metadata['year']) if metadata['year'].isdigit() else 0
            if 1980 <= year <= 2030:
                score += 0.5
        
        # Check text content indicators
        try:
            first_page_text = ""
            if len(pdf_reader.pages) > 0:
                first_page_text = pdf_reader.pages[0].extract_text().lower()
            
            academic_keywords = ['abstract', 'introduction', 'methodology', 'references', 'conclusion', 'keywords', 'doi']
            for keyword in academic_keywords:
                if keyword in first_page_text:
                    score += 0.3
            
            # Check for common academic structures
            if 'references' in first_page_text or len(pdf_reader.pages) > 5:
                score += 0.5
                
        except Exception:
            pass
        
        confidence = min(score / max_score, 1.0)
        is_academic = confidence > 0.4
        
        return is_academic, confidence
    
    def _split_into_chunks(self, text: str, chunk_size: int = 500) -> List[str]:
        """
        Split text into smaller chunks for better processing.
        
        Args:
            text: Text to split
            chunk_size: Approximate size of each chunk
            
        Returns:
            List of text chunks
        """
        # Split by sentences first
        sentences = re.split(r'[.!?]+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed chunk size, start new chunk
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _extract_context(self, text: str, query: str, context_length: int = 200) -> str:
        """
        Extract context around a query match.
        
        Args:
            text: Text to search in
            query: Query to find
            context_length: Number of characters of context on each side
            
        Returns:
            Context string
        """
        text_lower = text.lower()
        query_lower = query.lower()
        
        match_pos = text_lower.find(query_lower)
        if match_pos == -1:
            return text[:context_length * 2]  # Return beginning if no match
        
        start = max(0, match_pos - context_length)
        end = min(len(text), match_pos + len(query) + context_length)
        
        context = text[start:end]
        
        # Add ellipsis if we're not at the beginning/end
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    def get_library_stats(self) -> Dict:
        """
        Get statistics about the library.
        
        Returns:
            Statistics dictionary
        """
        total_files = len(self.library)
        total_pages = sum(len(pdf_data['pages']) for pdf_data in self.library.values())
        total_chars = sum(len(pdf_data['full_text']) for pdf_data in self.library.values())
        
        return {
            'total_files': total_files,
            'total_pages': total_pages,
            'total_characters': total_chars,
            'avg_pages_per_file': total_pages / total_files if total_files > 0 else 0
        }
