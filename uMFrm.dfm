object Form1: TForm1
  Left = 0
  Top = 0
  BorderStyle = bsSingle
  Caption = 'Form1'
  ClientHeight = 119
  ClientWidth = 944
  Color = clBtnFace
  Font.Charset = DEFAULT_CHARSET
  Font.Color = clWindowText
  Font.Height = -13
  Font.Name = 'Consolas'
  Font.Style = []
  Menu = mm
  OldCreateOrder = False
  PixelsPerInch = 96
  TextHeight = 15
  object Panel2: TPanel
    Left = 0
    Top = 0
    Width = 944
    Height = 119
    Align = alTop
    Color = clWhite
    ParentBackground = False
    TabOrder = 0
    ExplicitTop = 82
    ExplicitWidth = 934
    object ssGRC1: TSevenSeg
      Left = 230
      Top = 8
      Width = 216
      Height = 76
      Caption = ''
      ColorBackGnd = 9978683
      ColorScheme = csBWG
      ColorText = clWhite
      FrameStyle = fsLowered
      InterDigDist = 2
      Margin = 8
      NumDigits = 3
    end
    object ssGRU1: TSevenSeg
      Left = 8
      Top = 8
      Width = 216
      Height = 76
      Caption = ''
      ColorBackGnd = 9978683
      ColorScheme = csBWG
      ColorText = clWhite
      FrameStyle = fsLowered
      InterDigDist = 2
      Margin = 8
      NumDigits = 4
    end
    object Label1: TLabel
      Left = 207
      Top = 90
      Width = 56
      Height = 15
      Caption = 'Output 1'
    end
    object ssGRU2: TSevenSeg
      Left = 487
      Top = 6
      Width = 216
      Height = 76
      Caption = ''
      ColorBackGnd = 9978683
      ColorScheme = csBWG
      ColorText = clWhite
      FrameStyle = fsLowered
      InterDigDist = 2
      Margin = 8
      NumDigits = 4
    end
    object ssGRC2: TSevenSeg
      Left = 709
      Top = 6
      Width = 216
      Height = 76
      Caption = ''
      ColorBackGnd = 9978683
      ColorScheme = csBWG
      ColorText = clWhite
      FrameStyle = fsLowered
      InterDigDist = 2
      Margin = 8
      NumDigits = 3
    end
    object Label2: TLabel
      Left = 687
      Top = 88
      Width = 56
      Height = 15
      Caption = 'Output 2'
    end
    object Button1: TButton
      Left = 328
      Top = 88
      Width = 75
      Height = 25
      Caption = 'Button1'
      TabOrder = 0
    end
  end
  object comport: TComPort
    BaudRate = br115200
    Port = 'COM1'
    Parity.Bits = prOdd
    StopBits = sbOneStopBit
    DataBits = dbEight
    Events = [evRxChar, evTxEmpty, evRxFlag, evRing, evBreak, evCTS, evDSR, evError, evRLSD, evRx80Full]
    FlowControl.OutCTSFlow = False
    FlowControl.OutDSRFlow = False
    FlowControl.ControlDTR = dtrDisable
    FlowControl.ControlRTS = rtsDisable
    FlowControl.XonXoffOut = False
    FlowControl.XonXoffIn = False
    StoredProps = [spBasic]
    TriggersOnRxChar = True
    OnAfterOpen = comportAfterOpen
    Left = 88
  end
  object cdp: TComDataPacket
    OnCustomStop = HandleCustomStop
    Left = 128
  end
  object al: TActionList
    Left = 48
    object aComOpen: TAction
      Caption = 'Open'
      OnExecute = aComOpenExecute
    end
    object aComClose: TAction
      Caption = 'Close'
      OnExecute = aComCloseExecute
    end
    object aComSetup: TAction
      Caption = 'Setup'
      OnExecute = aComSetupExecute
    end
  end
  object mm: TMainMenu
    Left = 16
    object File1: TMenuItem
      Caption = 'File'
    end
    object erminal1: TMenuItem
      Caption = 'Terminal'
      object Open1: TMenuItem
        Action = aComOpen
      end
      object Close1: TMenuItem
        Action = aComClose
      end
      object Setup1: TMenuItem
        Action = aComSetup
      end
    end
  end
  object Timer1: TTimer
    Enabled = False
    Interval = 50
    OnTimer = Timer1Timer
    Left = 440
    Top = 72
  end
end
