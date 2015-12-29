unit uMFrm;

interface

uses
  Winapi.Windows, Winapi.Messages, System.SysUtils, System.Variants, System.Classes, Vcl.Graphics,
  Vcl.Controls, Vcl.Forms, Vcl.Dialogs, Vcl.ExtCtrls, Vcl.StdCtrls, CPortCtl,
  CPort, System.Actions, Vcl.ActnList, PS2000_struct, SDL_sevenseg, Vcl.Menus;

const AskQueue:array [0..1] of string = (#117#0#71#0#188, #117#1#71#0#189);
const teststr: string =  #133#0#71#1#1#100#0#30#0#1#80;

type
  TForm1 = class(TForm)
    comport: TComPort;
    cdp: TComDataPacket;
    al: TActionList;
    aComOpen: TAction;
    aComClose: TAction;
    aComSetup: TAction;
    Panel2: TPanel;
    ssGRC1: TSevenSeg;
    ssGRU1: TSevenSeg;
    Label1: TLabel;
    ssGRU2: TSevenSeg;
    ssGRC2: TSevenSeg;
    Label2: TLabel;
    mm: TMainMenu;
    File1: TMenuItem;
    erminal1: TMenuItem;
    Open1: TMenuItem;
    Close1: TMenuItem;
    Setup1: TMenuItem;
    Timer1: TTimer;
    Button1: TButton;
    procedure HandleCustomStop(Sender: TObject; const Str: String; var Pos: Integer);
    procedure aComSetupExecute(Sender: TObject);
    procedure aComCloseExecute(Sender: TObject);
    procedure aComOpenExecute(Sender: TObject);
    procedure comportAfterOpen(Sender: TObject);
    procedure Timer1Timer(Sender: TObject);
  private
    { Private declarations }

  public
    { Public declarations }
  end;



var
  Form1: TForm1;
  s: variant;

implementation

{$R *.dfm}

function xHexToBin(const HexStr: String): TBytes;
const HexSymbols = '0123456789ABCDEF';
var i, J: integer;
    B: Byte;
begin
  SetLength(Result, (Length(HexStr) + 1) shr 1);
  B:= 0;
  i :=  0;
  while I < Length(HexStr) do begin
    J:= 0;
    while J < Length(HexSymbols) do begin
      if HexStr[I + 1] = HexSymbols[J + 1] then Break;
      Inc(J);
    end;
    if J = Length(HexSymbols) then ; // error
    if Odd(I) then
      Result[I shr 1]:= B shl 4 + J
    else
      B:= J;
    Inc(I);
  end;
  if Odd(I) then Result[I shr 1]:= B;
end;

function HexToNumStr(const HexStr: String): string;
var
  t: tbytes;
  i: integer;
  s: string;
begin
  t := xHexToBin('75004700BC');
  for i := low(t) to high(t) do s := s + '#' + IntToStr(t[i]);
  Result := s;
end;

procedure TForm1.aComCloseExecute(Sender: TObject);
begin
  ComPort.Close;
end;

procedure TForm1.aComOpenExecute(Sender: TObject);
begin
  ComPort.Open;
end;

procedure TForm1.aComSetupExecute(Sender: TObject);
begin
  ComPort.ShowSetupDialog;
  ComPort.StoreSettings(stIniFile, ChangeFileExt(Application.ExeName, '.ini'));
end;

procedure TForm1.comportAfterOpen(Sender: TObject);
begin
  ComPort.WriteStr( AskQueue[ComPort.Tag]);
  ComPort.Tag := ComPort.Tag + 1;
  if ComPort.Tag > High(AskQueue) Then ComPort.Tag := 0;
end;

procedure TForm1.HandleCustomStop(Sender: TObject; const Str: String; var Pos: Integer);
var
  PSTelegram: RPSTelegram;
  FileName, CSVline: String;
  loggfile: TextFile;
begin
  if pos > 10 then begin
    PSTelegram.Load(str);

    Case PSTelegram.Node Of
      0: Begin
        ssGRU1.Caption := FloatToStr(PSTelegram.GRU);
        ssGRC1.Caption := FloatToStr(PSTelegram.GRC);
      End;
      1: Begin
        ssGRU2.Caption := FloatToStr(PSTelegram.GRU);
        ssGRC2.Caption := FloatToStr(PSTelegram.GRC);
      End;
    End;

    Try
      FileName := FormatDateTime('yyyy-mm-dd', Now()) + '.csv';
      AssignFile(loggfile, FileName);
      If FileExists(FileName) Then Append(loggfile)
      Else Rewrite(loggfile);

      CSVline :=
      FormatDateTime('yyyy-mm-dd', Now())  + #44 +
      FormatDateTime('hh:nn:ss.zzz', Now()) + #44 +
      ssGRU1.Caption + #44 +
      ssGRC1.Caption + #44 +
      ssGRU2.Caption + #44 +
      ssGRC2.Caption;

      WriteLn(LoggFile, CSVline);
    Finally
      CloseFile(loggfile);
    End;

    cdp.ResetBuffer;
    Timer1.Enabled := True;
  end;
end;

procedure TForm1.Timer1Timer(Sender: TObject);
begin
  Timer1.Enabled := False;
  if ComPort.Connected then ComPort.WriteStr( AskQueue[ComPort.Tag]);
  ComPort.Tag := ComPort.Tag + 1;
  if ComPort.Tag > High(AskQueue) Then ComPort.Tag := 0;
end;

end.
