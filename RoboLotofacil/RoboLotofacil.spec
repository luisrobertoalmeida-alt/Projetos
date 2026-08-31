# -*- mode: python ; coding: utf-8 -*-
"""
RoboLotofacil.spec
-------------------
Spec do PyInstaller para gerar o executável do RoboLotofacilPro.

Uso (no Windows, com pandas/requests/pyinstaller instalados no mesmo
Python usado para rodar o robô):
    pyinstaller RoboLotofacil.spec

Resultado: dist\\RoboLotofacil\\RoboLotofacil.exe (modo "onedir" -- o
.exe e seus arquivos de suporte ficam juntos numa pasta, editáveis).

Não empacota a pasta dados/ do repositório: config.py resolve
PASTA_DADOS para %USERPROFILE%\\Documents\\RoboLotofacilPro\\dados,
independente de onde o .exe está instalado -- então o robô encontra
sozinho o histórico/memória que você já tem hoje rodando via
`python main.py`, sem precisar copiar nada. config_v22.yaml é
empacotado porque v22_config.py o localiza relativo ao próprio pacote
(cai fora do alcance de PASTA_DADOS); se não empacotado, ConfigV22 cai
no fallback de defaults (ver docstring do módulo) -- não impede o robô
de funcionar, só faz os experimentais V22 usarem os valores padrão.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config_v22.yaml', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RoboLotofacil',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RoboLotofacil',
)
