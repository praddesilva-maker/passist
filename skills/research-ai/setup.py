from setuptools import setup, find_packages

setup(
    name="research-ai-skill",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0",
        "python-docx>=0.8.11",
        "python-pptx>=0.6.21", 
        "openpyxl>=3.0.0",
        "markdown>=3.3.0"
    ],
    python_requires=">=3.8",
    author="Personal Assistant Team",
    description="Research AI skill for passist framework with APA citation support and multi-format output",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)