# Avisos de Terceiros (Third-Party Notices)

O **Último Livro** (fork brasileiro do **Lastbook**, <https://github.com/Immortal-Protocols/lastbook> / <https://lastbook.org>) apoia-se nos softwares e dados listados abaixo. Cada componente mantém sua própria licença. As seções indicam se o componente está incluído neste repositório, empacotado nos aplicativos pelo build ou baixado apenas durante a configuração inicial.

**Conferido (Checked)** significa que a licença foi verificada no arquivo de licença ou nos metadados do pacote da versão exata usada nos builds.
**Upstream** significa que a licença foi obtida da documentação publicada pelo projeto original por não haver cópia local no momento do levantamento — confira esses itens antes de uma distribuição pública.

As versões correspondem às definições fixadas em `packaging/requirements*.txt`, `packaging/llm/*.sh`, `packaging/build_app_windows.sh` e `llm_local.py`.

## Incluídos neste repositório (vendored)

| Componente | Versão | Licença | Fonte | Verificação |
|---|---|---|---|---|
| pypdfium2 (`engine/vendor-macos/` no macOS; instalado via PyPI no build Windows) | 5.14.0 | Apache-2.0 ou BSD-3-Clause; arquivos de dados CC-BY-4.0 | https://github.com/pypdfium2-team/pypdfium2 | Conferido: `pypdfium2-5.14.0.dist-info/licenses/` |
| PDFium, dentro de `libpdfium.dylib` do pypdfium2 | conforme compilado por pdfium-binaries | BSD-3-Clause (The PDFium Authors) | https://pdfium.googlesource.com/pdfium, https://github.com/bblanchon/pdfium-binaries | Conferido: `BUILD_LICENSES/pdfium.txt`, `pdfium-binaries.txt` |
| Bibliotecas embutidas no PDFium: abseil, agg 2.3, fast_float, FreeType, ICU, Little CMS, libjpeg-turbo, OpenJPEG, libpng, LLVM libc, simdutf, zlib | conforme compilado | Cada uma sob sua própria licença (Apache-2.0, estilo BSD, FreeType/FTL, Unicode, MIT, IJG, zlib e outras) | ver cada arquivo | Conferido: textos completos em `engine/vendor-macos/pypdfium2-5.14.0.dist-info/licenses/data/darwin_arm64/BUILD_LICENSES/` |

## Empacotados nos aplicativos pelo build

| Componente | Versão | Licença | Fonte | Verificação |
|---|---|---|---|---|
| Python (runtime empacotado pelo PyInstaller) | 3.11.18 (Mac), 3.14.10 ou posterior 3.14 (Windows) | PSF-2.0 | https://www.python.org | Upstream |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later com exceção do PyInstaller, permitindo empacotar programas sob qualquer licença | https://github.com/pyinstaller/pyinstaller | Conferido: metadados do pacote |
| python-libzim | 3.13.1 (Mac), 3.13.0 (Windows) | **GPL-3.0-or-later** | https://github.com/openzim/python-libzim | Conferido: `libzim-3.13.1.dist-info/licenses/LICENSE` |
| libzim (C++, dentro do wheel do python-libzim) | 9 | GPL-2.0 | https://github.com/openzim/libzim | Upstream |
| Xapian e ICU 73, embutidos na libzim | conforme compilado | Xapian: GPL-2.0-or-later; ICU: Unicode License | https://xapian.org, https://icu.unicode.org | Upstream (ambos presentes no binário) |
| zstd e liblzma (xz), usados pela libzim | conforme compilado | zstd: BSD-3-Clause ou GPL-2.0; liblzma: 0BSD/domínio público | https://github.com/facebook/zstd, https://tukaani.org/xz/ | Upstream |
| NumPy | 2.4.6 (Mac), 2.5.4 (Windows) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org | Conferido: metadados do pacote (2.4.6) |
| Beautiful Soup 4 | 4.15.0 | MIT | https://www.crummy.com/software/BeautifulSoup/ | Conferido: metadados do pacote |
| soupsieve (usado pelo Beautiful Soup) | 3.0.4 | MIT | https://github.com/facelessuser/soupsieve | Conferido: metadados do pacote |
| PyObjC: pyobjc-core, Cocoa, WebKit (Mac) | 13.0 | MIT | https://github.com/ronaldoussoren/pyobjc | Conferido: metadados do pacote |
| onnxruntime (Windows) | 1.31.1 | MIT; seus componentes internos estão listados no `ThirdPartyNotices.txt` próprio | https://github.com/microsoft/onnxruntime | Conferido: metadados e avisos da 1.31.0 |
| Hugging Face tokenizers (Windows) | 0.23.3 | Apache-2.0; os crates Rust embutidos constam no SBOM (`dist-info/sboms`) | https://github.com/huggingface/tokenizers | Conferido: metadados do pacote |
| pythonnet (Windows) | 3.2.1 | MIT | https://github.com/pythonnet/pythonnet | Upstream |
| clr_loader (Windows) | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader | Upstream |
| Microsoft WebView2 SDK: `Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll`, `WebView2Loader.dll` (Windows) | 1.0.3856.49 | Licença da Microsoft no pacote NuGet (`LICENSE.txt`), que permite redistribuir estes arquivos com o aplicativo | https://www.nuget.org/packages/Microsoft.Web.WebView2 | Upstream: conferir `LICENSE.txt` do pacote antes do lançamento |
| Microsoft Edge WebView2 Runtime (Windows) | instalado pelo Windows | Termos de licença de software da Microsoft | https://developer.microsoft.com/microsoft-edge/webview2/ | Não empacotado: o aplicativo usa a cópia fornecida pelo Windows |
| llama.cpp e ggml, em `lastbook-llm` (executor opcional da IA local) | tag b12032 (dde879bc) | MIT (Copyright dos autores ggml) | https://github.com/ggml-org/llama.cpp | Conferido: `LICENSE`; acompanha o executor como `LICENSE-llama.cpp.txt` |
| nlohmann/json, usado por `common/` do llama.cpp | incluído na tag b12032 | MIT | https://github.com/nlohmann/json | Conferido: `licenses/LICENSE-jsonhpp` |
| LLVM libc++, libunwind, OpenMP runtime (`libc++.dll`, `libunwind.dll`, `libomp.dll`, executor Windows) | llvm-mingw 20261020 | Apache-2.0 WITH LLVM-exception | https://github.com/mstorsjo/llvm-mingw | Conferido: acompanha o binário como `LICENSE-llvm-mingw.txt` |

Ferramentas apenas de build (`uv`, `CMake`, `Ninja`, `glslc/shaderc`, cabeçalhos Vulkan e SPIR-V, `pyinstaller-hooks-contrib`, `altgraph`, `macholib`, `setuptools`, `packaging`) são usadas na construção dos aplicativos e nenhum código delas é distribuído exceto conforme permitido por suas licenças. O carregador Vulkan (`vulkan-1.dll`) vem com o driver de vídeo e não é empacotado.

## Baixados pela configuração inicial, nunca empacotados no app

| Componente | Versão | Licença | Fonte | Verificação |
|---|---|---|---|---|
| Gemma 4 26B A4B instruct, quantização GGUF por Unsloth (`gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`) | revisão fixada em `llm_local.py` | Apache-2.0, conforme model card | https://huggingface.co/unsloth (lançamento Gemma 4 do Google) | Upstream: conferir o model card e licença antes de redistribuir |
| BAAI bge-small-en-v1.5 (ONNX), busca por significado | conforme fixado | MIT, conforme model card | https://huggingface.co/BAAI/bge-small-en-v1.5 | Upstream: a cópia local não traz arquivo de licença ao lado |

## Site / Fontes

| Componente | Licença | Fonte | Verificação |
|---|---|---|---|
| Atkinson Hyperlegible Next (`website/fonts/`) | SIL Open Font License 1.1 | https://github.com/googlefonts/atkinson-hyperlegible-next | Conferido: `website/fonts/OFL.txt` |
| Nunito (`website-next/fonts/`) | SIL Open Font License 1.1 | https://github.com/googlefonts/nunito | Conferido: `website-next/fonts/OFL.txt` |

## Conteúdo da biblioteca e dados geográficos

Os manuais, vídeos, enciclopédias e dados cartográficos dos pacotes da biblioteca não fazem parte deste repositório. Cada pacote contém uma página de Fontes e permissões detalhando o editor e os termos de cada item. O mapa offline utiliza dados do OpenStreetMap (ODbL, © OpenStreetMap contributors), dados de referência dos EUA no upstream (USGS, NOAA e USACE, conforme creditado no mapa) e a malha territorial das 27 unidades federativas do Brasil proveniente de dados públicos do IBGE em `web/geographic-context.json`.
