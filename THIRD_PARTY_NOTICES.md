# Third-party notices

## autobox: ArcGIS toolbox serialization pattern

`tools/build_toolbox.py` adapts the small ArcGIS `.atbx` Zip/JSON serialization pattern from [autobox](https://github.com/realiii/autobox), inspected commit [`298c57385cdede8b3417cc7b736a066febd874a9`](https://github.com/realiii/autobox/tree/298c57385cdede8b3417cc7b736a066febd874a9). In particular, the toolbox/tool content-resource structure, parameter JSON structure and relative execution-link convention follow its `toolbox.py`, `script.py`, `parameter.py`, `constant.py` and `filter.py` examples. This repository contains a small purpose-built builder, not an installation or vendored copy of the complete autobox package.

The upstream license is reproduced below. Retain this notice with distributions containing the builder or generated toolbox.

> MIT License
>
> Copyright (c) 2024-2025 Integrated Informatics (USA) Inc.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Research references

The local wind benchmark independently implements the mathematical equations in Boose, E.R., Serrano, M.I. & Foster, D.R. (2004), *Landscape and regional impacts of hurricanes in Puerto Rico*, Ecological Monographs 74, 335-352. DOI https://doi.org/10.1890/02-4057. Its four radius/profile scenarios also follow that study.

Numerical conventions were checked against the author's [HurreconPython](https://github.com/hurrecon-model/HurreconPython) scalar speed function. The reviewed source SHA256 is `193fa153cf002e5229a6e1035769da9a1a4b446fb7eec9b4131e1c53a813880d`. A temporary in-memory comparison of 1,000 cases agreed to floating-point precision. Source from that GPL-3.0 engine is not included in this distribution. Preserve its license and notices if incorporating its code in future work.

The processing guide also references CLIMADA, Tropycal and tcwind as research alternatives. Record their pinned versions, licenses and notices before incorporating code or dependencies.
