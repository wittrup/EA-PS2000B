unit PS2000_struct;

interface

uses System.Classes, System.SysUtils, bfRec;

type
  RPSStartDelimiter = record
  private
    Flags: Cardinal;
    function GetBits(const aIndex: Integer): Integer;
    procedure SetBits(const aIndex: Integer; const aValue: Integer);
  public
    property Data_Length: Integer index $0003 read GetBits write SetBits; // 4 bits@offset 0, Data length -1 of the data in the data field of the telegram (bytes 3-18)
    property Direction: Integer index $0104 read GetBits write SetBits;   // 1 bits@offset 4, 0= Telegram from device to control unit, 1= Telegram from control unit to device
    property Cast_type: Integer index $0105 read GetBits write SetBits;   // 1 bits@offset 5, 1= Cast type, for sending/querying it must be set to 1, in answers it will be 0
    property Transmission: Integer index $0206 read GetBits write SetBits;// 2 bits@offset 6, 00 = Reserved, 01 = Query data, 10 = Answer to a query, 11 = Send data
    property SD: Cardinal write Flags;
  end;

type ROBJ_Status = packed record
  private
    Query_device_state: Byte;
    Status_byte: Byte;
    Voltage_percent: Word;
    Current_percent: Word;
end;

type RPSTelegram = record
  private
    { Private declarations }
    fSD: RPSStartDelimiter; // Byte 0: SD (start delimiter)
    fDN: Byte;              // Byte 1: DN (device node)
    fOBJ: Byte;             // Byte 2: OBJ
    fDATA: TBytes;          // Byte 3 - 18: Data field
    fCS: Word;              // Word x: CS (check sum)

    fOBJ_Status: ROBJ_Status;
  public
    { Public declarations }
    procedure Load(const str: string);
    function Dump: String;
    function GRU: Double;
    function GRC: Double;
    property Node: Byte read fDN;
end;

implementation

function RPSTelegram.GRU: Double;
begin
  Result := 0;
  if fOBJ = 71 then begin
    Result := 42 * fOBJ_Status.Voltage_percent / 25600;
  end;
end;

function RPSTelegram.GRC: Double;
begin
  Result := 0;
  if fOBJ = 71 then begin
    Result :=  6 * fOBJ_Status.Current_percent / 25600;
  end;
end;

procedure RPSTelegram.Load(const str: string);
var
  len, i: integer;
begin
  len := Length(str);
  if len > 4 then begin
    fSD.SD := Byte(str[1]);
    fDN :=    Byte(str[2]);
    fOBJ :=   Byte(str[3]);
    SetLength(fData, fSD.Data_Length);
    for i := 4 to fSD.Data_Length + 4 do fData[i - 4] := Byte(str[i]);
    WordRec(fCS).Hi := Byte(str[fSD.Data_Length + 4]);
    WordRec(fCS).Lo := Byte(str[fSD.Data_Length + 5]);

    Case fOBJ of
      71: Begin //  Status + Actual values
        WordRec(fOBJ_Status.Voltage_percent).Hi := fData[2];
        WordRec(fOBJ_Status.Voltage_percent).Lo := fData[3];
        WordRec(fOBJ_Status.Current_percent).Hi := fData[4];
        WordRec(fOBJ_Status.Current_percent).Lo := fData[5];
      End;
    End;
  end;
end;

function RPSTelegram.Dump: String;
var
  s: string;
begin
  s :=s+Format('Data length  : %d'#13#10, [fSD.Data_Length]);
  s :=s+Format('Direction    : %d'#13#10, [fSD.Direction]);
  s :=s+Format('Cast type    : %d'#13#10, [fSD.Cast_type]);
  s :=s+Format('Transmission : %d'#13#10, [fSD.Transmission]);
  s :=s+Format('Device node  : %d'#13#10, [fDN]);
  s :=s+Format('OBJ          : %d'#13#10, [fOBJ]);
  s :=s+Format('Check sum    : %d'#13#10, [fCS]);
  Result := s;
end;

function RPSStartDelimiter.GetBits(const aIndex: Integer): Integer;
begin
  Result := GetDWordBits(Flags, aIndex);
end;

procedure RPSStartDelimiter.SetBits(const aIndex: Integer; const aValue: Integer);
begin
  SetDWordBits(Flags, aIndex, aValue);
end;

end.
