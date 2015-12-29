unit bfRec;

interface

uses System.Classes, System.Types;

function GetDWordBits(const Bits: DWORD; const aIndex: Integer): Integer;
procedure SetDWordBits(var Bits: DWORD; const aIndex: Integer; const aValue: Integer);

implementation

function GetDWordBits(const Bits: DWORD; const aIndex: Integer): Integer;
begin
  Result := (Bits shr (aIndex shr 8))       // offset
            and ((1 shl Byte(aIndex)) - 1); // mask
end;

procedure SetDWordBits(var Bits: DWORD; const aIndex: Integer; const aValue: Integer);
var
  Offset: Byte;
  Mask: Integer;
begin
  Mask := ((1 shl Byte(aIndex)) - 1);
  Assert(aValue <= Mask);

  Offset := aIndex shr 8;
  Bits := (Bits and (not (Mask shl Offset)))
          or DWORD(aValue shl Offset);
end;

end.
